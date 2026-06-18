"""工作流引擎 v3 — 集成所有功能模块

- 代码执行 (Python/R/MATLAB/Julia) + 失败自动修复重试
- 文献检索 (OpenAlex + Tavily)
- RAG 知识库检索
- HIL 人机协作
- 质量评估 (Shadow/Full 模式)
- A2A Handoff 容错
- 中英文双语支持
"""

import json
import os
import asyncio
import re
from typing import Dict, Any, Optional, Callable, List
from loguru import logger
from app.services.redis_manager import redis_manager
from app.core.llm.litellm_provider import LLMFactory
from app.core.engine.interpreter import LocalInterpreter, ExecutionResult
from app.core.engine.literature import LiteratureSearch, Paper
from app.core.engine.hil import hil_manager, DecisionAction
from app.core.engine.rag import rag_engine
from app.core.engine.evaluator import FeedbackRunner, EvalMode
from app.core.engine.i18n import i18n, PromptSet
from app.core.engine.tavily_search import tavily_engine


class WorkflowEngine:
    """工作流引擎 v3 — 全功能集成版"""

    MAX_RETRIES = 3
    CODE_BLOCK_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.progress_callback = None
        self.log_callback = None
        self.checkpoint_callback = None  # 断点回调：每阶段完成后调用
        self.llm_config = config.get("llm", {})
        self.has_api_key = bool(self.llm_config.get("api_key", "").strip())
        # 实例级缓存（每个任务独立，避免并发污染）
        self._llm_cache: Dict[str, Any] = {}
        self._response_cache: Dict[str, str] = {}
        self.MAX_CACHE_SIZE = 50
        self.task_id = None
        self.interpreter = LocalInterpreter(timeout=120)
        self.literature = LiteratureSearch()
        self.hil_enabled = config.get("hil_enabled", False)
        self.language = config.get("language", "zh")  # zh / en
        self.eval_mode = EvalMode.SHADOW if config.get("eval_shadow", True) else EvalMode.FULL
        self.use_rag = config.get("use_rag", True)
        self.use_tavily = config.get("use_tavily", False)
        self._cancel_event = asyncio.Event()  # 取消信号
        self._checkpoint: Dict[str, Any] = {}  # 断点数据

        # 获取对应语言的提示词
        self.prompts = i18n.get_prompts(self.language)

        # 初始化评估器
        self.evaluator = FeedbackRunner(mode=self.eval_mode)
        self._eval_history = []

    # ── callbacks ──────────────────────────────────────────

    def set_callbacks(self, progress_callback=None, log_callback=None, checkpoint_callback=None):
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.checkpoint_callback = checkpoint_callback

    def cancel(self):
        """发送取消信号，工作流将在下一个检查点停止"""
        self._cancel_event.set()

    async def _check_cancelled(self):
        """检查是否被取消，如果是则保存断点并抛出 CancelledError"""
        if self._cancel_event.is_set():
            # 保存断点到数据库
            if self.checkpoint_callback and self._checkpoint:
                await self.checkpoint_callback(self._checkpoint)
            raise asyncio.CancelledError("任务已被用户暂停")

    def _update_progress(self, phase: str, progress: int, message: str = ""):
        if self.progress_callback:
            self.progress_callback(phase, progress, message)

    def _log(self, agent: str, message: str, level: str = "info"):
        if self.log_callback:
            self.log_callback(agent, message, level)

    async def _publish(self, content: str, msg_type: str = "info"):
        if self.task_id:
            await redis_manager.publish_message(
                self.task_id, {"content": content, "type": msg_type}
            )

    # ── HIL 人机协作 ────────────────────────────────────

    async def _hil_checkpoint(
        self,
        phase: str,
        agent: str,
        question: str,
        preview: str,
        timeout: int = 300,
    ) -> str:
        """
        创建 HIL 检查点并等待用户决策。
        返回用户决策动作（confirm/regenerate/edit/skip/abort）。
        """
        if not self.hil_enabled:
            return DecisionAction.CONFIRM.value

        cp_id = hil_manager.create_checkpoint(
            phase=phase,
            agent=agent,
            question=question,
            preview=preview,
            timeout=timeout,
        )

        self._log(agent, f"等待用户决策: {question}", "warning")
        await self._publish(f"⏸️ {agent} 需要你的决策: {question}", "hil")

        checkpoint = await hil_manager.wait_for_decision(cp_id, timeout)
        action = checkpoint.user_action if checkpoint else DecisionAction.CONFIRM.value

        self._log(agent, f"用户决策: {action}")
        await self._publish(f"用户选择了: {action}", "info")

        return action

    # ── LLM 调用（带重试） ────────────────────────────────

    async def _chat(self, llm, system: str, user: str, max_tokens: int = 1500, use_cache: bool = True) -> str:
        """调用 LLM，带重试、缓存和 token 控制"""
        # 检查缓存
        if use_cache:
            ck = self._cache_key(system, user)
            if ck in self._response_cache:
                logger.info(f"LLM cache hit, saved ~{max_tokens} tokens")
                return self._response_cache[ck]

        for attempt in range(self.MAX_RETRIES):
            try:
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
                resp = await llm.chat(messages, max_tokens=max_tokens)
                content = resp["content"]

                # 写入缓存
                if use_cache and len(self._response_cache) < self.MAX_CACHE_SIZE:
                    self._response_cache[ck] = content
                return content
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}): {e}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

    def _extract_code(self, text: str) -> str:
        """从 LLM 回复中提取代码块"""
        m = self.CODE_BLOCK_RE.search(text)
        return m.group(1).strip() if m else text.strip()

    # ── 代码执行 ──────────────────────────────────────────

    async def _execute_code(self, code: str, language: str, working_dir: str = None) -> ExecutionResult:
        """执行代码，失败后让 LLM 修复并重试"""
        for attempt in range(self.MAX_RETRIES):
            result = await self.interpreter.execute(code, language, working_dir)
            if result.success:
                return result
            logger.warning(f"Code execution failed (attempt {attempt+1}): {result.error[:200]}")
            if attempt < self.MAX_RETRIES - 1:
                code = await self._fix_code(code, result.error, language)
        return result

    async def _fix_code(self, code: str, error: str, language: str) -> str:
        """让 LLM 修复代码"""
        try:
            llm = self._get_llm("coder")
            fixed = await self._chat(
                llm,
                f"你是{language}代码修复专家。只返回修复后的完整代码，不要解释。",
                f"以下代码执行报错，请修复：\n\n```{language}\n{code}\n```\n\n错误信息：\n{error}",
                max_tokens=3000,
            )
            return self._extract_code(fixed)
        except Exception:
            return code

    # ── 图表管线 ──────────────────────────────────────────

    async def _run_chart_pipeline(
        self,
        chart_configs: List[Dict[str, Any]],
        problem_text: str = "",
        model: str = "",
        analysis: Dict[str, Any] = None,
        exec_result = None,
        language: str = "python",
    ) -> Dict[str, Any]:
        """执行图表管线 — 串联生成多个可视化图表

        Args:
            chart_configs: 图表配置列表，每项包含:
                - skill_id: Skill ID（如 chart-line, chart-scatter, flow-modeling）
                - params: 传给 Skill 的参数
            problem_text: 原始问题文本
            model: 建模结果
            analysis: 问题分析
            exec_result: 代码执行结果
            language: 编程语言

        Returns:
            字典，key=skill_id, value={success, code, execution_result}
        """
        results = {}

        for i, config in enumerate(chart_configs):
            skill_id = config.get("skill_id", "chart-line")
            params = config.get("params", {})

            # 自动填充上下文参数
            if not params.get("data") and problem_text:
                params["data"] = f"问题：{problem_text[:200]}"
            if not params.get("title"):
                params["title"] = f"图表 {i+1}: {skill_id}"

            self._log("chart_pipeline", f"[{i+1}/{len(chart_configs)}] 生成 {skill_id}...")
            await self._publish(f"📈 [{i+1}/{len(chart_configs)}] 正在生成 {skill_id}...")
            self._update_progress("charting", int(10 + 80 * i / len(chart_configs)))

            try:
                # 构建 prompt
                skill = self._get_skill_prompt(skill_id)
                user_message = self._build_chart_user_message(skill_id, params)

                # 调用 LLM
                llm = self._get_llm("coder")
                code = await self._chat(
                    llm,
                    skill or self.prompts.coder.format(language=language),
                    user_message,
                    max_tokens=4000,
                    use_cache=False,  # 图表不缓存（每次可能不同）
                )

                # 提取代码
                if skill_id.startswith("flow-"):
                    import re
                    m = re.search(r"```mermaid\s*\n(.*?)```", code, re.DOTALL)
                    extracted = m.group(1).strip() if m else code
                    results[skill_id] = {
                        "success": True,
                        "code": "",
                        "mermaid": extracted,
                        "execution_result": None,
                    }
                else:
                    python_code = self._extract_code(code)

                    # 执行代码（如果配置要求）
                    exec_output = None
                    try:
                        exec_output = await self.interpreter.execute(python_code, language)
                        results[skill_id] = {
                            "success": exec_output.success,
                            "code": python_code,
                            "execution_result": {
                                "success": exec_output.success,
                                "output": exec_output.output[:1000] if exec_output.output else "",
                                "error": exec_output.error[:300] if exec_output.error else "",
                                "figures": exec_output.figures or [],
                            },
                        }
                    except Exception as e:
                        results[skill_id] = {
                            "success": False,
                            "code": python_code,
                            "execution_result": {"success": False, "error": str(e)[:300]},
                        }

                self._log("chart_pipeline", f"  {skill_id} {'✓' if results[skill_id].get('success') else '✗'}")
            except Exception as e:
                logger.warning(f"图表管线 [{skill_id}] 失败: {e}")
                results[skill_id] = {"success": False, "error": str(e)[:300]}

        return results

    def _get_skill_prompt(self, skill_id: str) -> Optional[str]:
        """从 SkillManager 获取 Skill 的 system_prompt"""
        try:
            from app.services.skill_manager import skill_manager
            skill = skill_manager.get_skill(skill_id)
            if skill:
                return skill.system_prompt
        except Exception:
            pass
        return None

    def _build_chart_user_message(self, skill_id: str, params: Dict[str, Any]) -> str:
        """构建图表生成的用户消息"""
        if skill_id.startswith("flow-"):
            description = params.get("description", params.get("data", "请描述流程"))
            return f"请生成 Mermaid 流程图：\n\n{description}"

        chart_names = {
            "chart-line": "折线图",
            "chart-bar": "分组柱状图",
            "chart-scatter": "密度散点图",
            "chart-heatmap": "热力图",
            "chart-box": "箱线图+小提琴图",
            "chart-contour": "等高线图",
            "chart-radar": "雷达图",
            "chart-surface3d": "3D曲面图",
            "chart-sankey": "桑基图",
            "chart-network": "网络拓扑图",
        }
        chart_type = chart_names.get(skill_id, "图表")

        parts = [f"请生成一个学术级的{chart_type}。"]
        for key, val in params.items():
            if val:
                parts.append(f"{key}：{val}")
        return "\n".join(parts)

    # ── 文献检索 ──────────────────────────────────────────

    def _get_default_chart_pipeline(
        self, problem_text: str, analysis: str = ""
    ) -> List[Dict[str, Any]]:
        """根据问题类型自动推荐默认图表集

        分析问题文本关键词，返回合理的默认图表配置列表。
        作为 config.json 未配置 chart_pipeline 时的智能回退。
        """
        text = (problem_text + " " + (analysis or "")).lower()

        # 关键词 → 推荐图表映射
        keyword_chart_map = {
            "预测": ["chart-line", "chart-scatter"],
            "回归": ["chart-scatter", "chart-line"],
            "分类": ["chart-bar", "chart-heatmap"],
            "优化": ["chart-line", "chart-contour"],
            "聚类": ["chart-scatter", "chart-heatmap"],
            "评价": ["chart-radar", "chart-bar"],
            "时间序列": ["chart-line", "chart-bar"],
            "网络": ["chart-network", "chart-bar"],
            "风险": ["chart-heatmap", "chart-bar"],
            "相关性": ["chart-heatmap", "chart-scatter"],
            "分布": ["chart-box", "chart-scatter"],
            "对比": ["chart-bar", "chart-radar"],
        }

        # 匹配问题类型
        matched_charts = set()
        for keyword, charts in keyword_chart_map.items():
            if keyword in text:
                matched_charts.update(charts)

        # 至少生成 2 个基础图表
        if not matched_charts:
            matched_charts = {"chart-line", "chart-bar"}

        # 去重并构造配置
        chart_configs = []
        for skill_id in list(matched_charts)[:4]:  # 最多 4 个
            chart_configs.append({"skill_id": skill_id, "params": {}})

        return chart_configs

    async def _search_literature(self, topic: str, limit: int = 5) -> List[Paper]:
        """搜索相关文献（CNKI 优先，OpenAlex 回退）"""
        papers = []
        # 优先使用知网（中国网络环境可用）
        try:
            papers = await self.literature.search_math_modeling(
                topic, limit, source="cnki"
            )
            if papers:
                logger.info(f"知网检索到 {len(papers)} 篇文献")
                return papers
        except Exception as e:
            logger.warning(f"知网搜索失败: {e}")

        # 回退：OpenAlex
        try:
            papers = await self.literature.search_math_modeling(
                topic, limit, source="openalex"
            )
            if papers:
                logger.info(f"OpenAlex 检索到 {len(papers)} 篇文献")
        except Exception as e:
            logger.warning(f"OpenAlex 搜索失败: {e}")

        return papers

    def _format_references(self, papers: List[Paper]) -> str:
        """格式化参考文献（GB/T 7714 风格）"""
        if not papers:
            return ""
        lines = []
        for i, p in enumerate(papers, 1):
            authors = ", ".join(p.authors[:3])
            if len(p.authors) > 3:
                authors += " 等"
            ref = f"[{i}] {authors}. {p.title}"
            if p.journal:
                ref += f"[J]. {p.journal}"
            ref += f", {p.year}"
            if p.doi:
                ref += f". DOI: {p.doi}"
            lines.append(ref)
        return "\n".join(lines)

    # ── LLM 工厂 ─────────────────────────────────────────

    def _load_agent_config(self, agent_name: str = "coordinator") -> dict:
        """从 config.json 加载指定 Agent 的 LLM 配置（支持独立模型）"""
        from app.utils.llm_config import load_llm_config
        llm_cfg = load_llm_config(agent_name)
        return {
            "apiKey": llm_cfg.api_key,
            "baseUrl": llm_cfg.base_url,
            "modelId": llm_cfg.model,
            "apiType": llm_cfg.api_type,
        }

    def _create_llm(self, agent_name: str = "coordinator"):
        """为指定 Agent 创建 LLM 实例（每个 Agent 可用不同模型降本）"""
        from app.utils.llm_config import LLMConfig

        # 优先从 config.json 按 agent 加载
        try:
            agent_cfg = self._load_agent_config(agent_name)
            llm_cfg = LLMConfig.from_settings_config(agent_cfg)
        except Exception:
            # 回退到传入的配置（兼容旧逻辑）
            if isinstance(self.llm_config, dict) and "llm" in self.llm_config:
                inner = self.llm_config["llm"]
                llm_cfg = LLMConfig(
                    api_key=inner.get("api_key", inner.get("apiKey", "")),
                    base_url=inner.get("base_url", inner.get("baseUrl", None)),
                    model=inner.get("model", inner.get("modelId", "deepseek-chat")),
                    api_type=inner.get("api_type", inner.get("apiType", "openai")),
                )
            else:
                llm_cfg = LLMConfig.from_settings_config(self.llm_config)

        llm_conf = {
            "apiKey": llm_cfg.api_key,
            "baseUrl": llm_cfg.base_url,
            "modelId": llm_cfg.model,
            "apiType": llm_cfg.api_type,
        }
        return LLMFactory.create_from_config(llm_conf)

    # ── 主流程 ────────────────────────────────────────────

    async def run(self, problem_text: str, language: str = "python", task_id: str = None, checkpoint: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        self.task_id = task_id

        # 从断点恢复：使用已保存的部分结果
        if checkpoint and checkpoint.get("completed_stages"):
            result = checkpoint.get("partial_result", {})
            if not result:
                result = {"analysis": None, "model": None, "code": None, "execution_result": None, "paper": None, "literature": None}
            self._log("system", f"🔄 从断点恢复，已完成阶段: {', '.join(checkpoint['completed_stages'])}")
            await self._publish(f"🔄 从断点恢复（已完成: {', '.join(checkpoint['completed_stages'])}）")
        else:
            result = {"analysis": None, "model": None, "code": None, "execution_result": None, "paper": None, "literature": None}

        if not self.has_api_key:
            error_msg = "未配置 API Key，请在「设置 → API Key」中配置有效的 API Key 后重试"
            self._log("system", f"❌ {error_msg}", "error")
            await self._publish(f"❌ {error_msg}", "error")
            raise RuntimeError(error_msg)

        self._log("system", "🚀 使用真实 LLM 模式运行")

        try:
            return await self._run_real(problem_text, language, result, checkpoint=checkpoint, **kwargs)
        except asyncio.CancelledError:
            self._log("system", "⏸️ 任务已暂停，断点已保存")
            await self._publish("⏸️ 任务已暂停，可从断点恢复")
            # 保存最终断点
            if self.checkpoint_callback and self._checkpoint:
                await self.checkpoint_callback(self._checkpoint)
            result["status"] = "paused"
            result["_checkpoint"] = self._checkpoint
            return result
        except Exception as e:
            error_msg = str(e)
            # 分类错误信息，提供针对性的用户友好提示
            if "Authentication" in error_msg or "auth" in error_msg.lower() or "401" in error_msg:
                friendly = f"API Key 认证失败，请检查 Key 是否正确且未过期。技术详情: {error_msg[:200]}"
            elif "rate" in error_msg.lower() or "limit" in error_msg.lower() or "429" in error_msg:
                friendly = f"API 调用频率过高，请稍后重试。技术详情: {error_msg[:200]}"
            elif "timeout" in error_msg.lower() or "connect" in error_msg.lower():
                friendly = f"无法连接到 LLM 服务，请检查网络连接。技术详情: {error_msg[:200]}"
            else:
                friendly = f"LLM 调用失败。技术详情: {error_msg[:300]}"

            self._log("system", f"❌ {friendly}", "error")
            await self._publish(f"❌ {friendly}", "error")
            raise RuntimeError(friendly) from e

    # ── LLM 缓存（已移至 __init__ 实例级） ─────────────────

    def _get_llm(self, agent_name: str = "coordinator"):
        """获取或创建指定 Agent 的 LLM 实例（带缓存，每个 Agent 可用不同模型降本）"""
        if agent_name not in self._llm_cache:
            self._llm_cache[agent_name] = self._create_llm(agent_name)
        return self._llm_cache[agent_name]

    def _cache_key(self, system: str, user: str) -> str:
        import hashlib
        raw = f"{system}|||{user}"
        return hashlib.md5(raw.encode()).hexdigest()

    # ── 真实模式 ──────────────────────────────────────────

    async def _run_real(self, problem_text: str, language: str, result: Dict[str, Any], checkpoint: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        prompts = self.prompts  # 使用对应语言的提示词

        # 用户特殊要求（将注入到所有 Agent）
        notes = kwargs.get("notes", "")
        notes_context = f"\n\n## 用户特殊要求（必须遵守）\n{notes}" if notes else ""

        # 断点续传：获取已完成阶段
        completed_stages = set(checkpoint.get("completed_stages", [])) if checkpoint else set()
        self._checkpoint = checkpoint or {}
        self._checkpoint.setdefault("completed_stages", [])
        self._checkpoint.setdefault("partial_result", result)

        # 每个阶段的 token 预算（控制成本）
        # deepseek-v4-pro 支持最大输出 384,000 tokens，以下预算在安全范围内
        TOKEN_BUDGET = {
            "analysis": 8000,    # 问题分析（含附件内容需要更多 tokens）
            "modeling": 10000,   # 数学建模（完整推导和公式）
            "coding": 6000,      # 代码生成（含完整注释和可视化）
            "paper": 32000,      # 论文撰写（完整论文 ~8000-16000 字）
            "retry": 6000,       # 重试
        }

        async def _save_checkpoint(stage: str):
            """保存当前阶段断点"""
            if stage not in self._checkpoint["completed_stages"]:
                self._checkpoint["completed_stages"].append(stage)
            self._checkpoint["partial_result"] = result
            if self.checkpoint_callback:
                await self.checkpoint_callback(self._checkpoint)

        try:
            # 🔍 RAG 知识库检索
            rag_context = ""
            if self.use_rag:
                try:
                    await rag_engine.initialize()
                    rag_docs = await rag_engine.search_for_modeling(problem_text, top_k=3)
                    if rag_docs:
                        rag_context = "\n\n## 相关知识库参考\n\n"
                        for doc in rag_docs:
                            rag_context += f"### {doc['title']}\n{doc['content'][:500]}\n\n"
                        self._log("rag", f"检索到 {len(rag_docs)} 篇相关知识")
                        await self._publish(f"RAG 知识库检索完成 ({len(rag_docs)} 篇参考)")
                except Exception as e:
                    logger.warning(f"RAG 检索失败: {e}")

            # ⏭️ 断点续传：跳过已完成阶段
            skip_analysis = "analysis" in completed_stages

            # 1️⃣ 分析问题
            if not skip_analysis:
                self._log("coordinator", "正在分析问题...")
                await self._publish("协调器正在分析问题...")
                self._update_progress("analysis", 0)

            # 智能截断：超长问题文本保留首尾（附件可能在尾部）
            MAX_PROBLEM_CHARS = 12000
            truncated_problem = problem_text
            if len(problem_text) > MAX_PROBLEM_CHARS:
                half = MAX_PROBLEM_CHARS // 2
                truncated_problem = (
                    problem_text[:half]
                    + f"\n\n...（中间省略 {len(problem_text) - MAX_PROBLEM_CHARS} 字符）...\n\n"
                    + problem_text[-half:]
                )
                self._log("coordinator", f"问题文本过长（{len(problem_text)} 字符），已智能截断为 {len(truncated_problem)} 字符")

            analysis = await self._chat(
                self._get_llm("coordinator"),
                prompts.coordinator + notes_context,
                f"请深入分析以下数学建模问题，提取所有关键信息（数据、约束、目标、表格数据等），输出结构化分析：\n\n{truncated_problem}\n\n{rag_context}" if rag_context else f"请深入分析以下数学建模问题，提取所有关键信息（数据、约束、目标、表格数据等），输出结构化分析：\n\n{truncated_problem}",
                max_tokens=TOKEN_BUDGET["analysis"],
            )
            result["analysis"] = {"content": analysis}
            self._update_progress("analysis", 100)

            # HIL: 分析阶段检查点
            hil_action = await self._hil_checkpoint(
                "analysis", "coordinator",
                "问题分析已完成，是否继续文献检索与建模？",
                analysis[:500],
            )
            if hil_action == "abort":
                result["status"] = "aborted"
                return result
            if hil_action == "regenerate":
                self._log("coordinator", "用户要求重新分析")
                analysis = await self._chat(
                    self._get_llm("coordinator"),
                    prompts.coordinator,
                    f"请根据用户反馈重新分析以下数学建模问题：\n\n{problem_text}\n\n用户反馈：请从不同角度重新分析",
                    max_tokens=TOKEN_BUDGET["retry"],
                )
                result["analysis"] = {"content": analysis}
            if hil_action == "edit":
                self._log("coordinator", "用户已编辑分析内容")

            # 📊 评估分析质量 (Shadow 模式)
            self._log("evaluator", "评估分析质量...")
            analysis_eval = self.evaluator.evaluator.evaluate_analysis(analysis, problem_text)
            self._log("evaluator", f"分析评分: {analysis_eval.score}/100 {'✓' if analysis_eval.passed else '⚠️'}")

            # 2️⃣ 文献检索 + Tavily 搜索
            self._log("coordinator", "正在检索相关文献...")
            await self._publish("正在检索相关文献...")
            topic = analysis[:100]
            papers = await self._search_literature(topic)

            # 保存文献到独立文献表（DOI 去重，跨任务复用）
            saved_count = 0
            try:
                from app.models.database import SessionLocal as _SessionLocal
                _lit_db = _SessionLocal()
                try:
                    self.literature.set_db_session(_lit_db)
                    await self.literature._save_to_db(papers, topic, self.task_id)
                    saved_count = len(papers)
                finally:
                    _lit_db.close()
            except Exception as e:
                logger.warning(f"保存文献到独立表失败: {e}")

            # Tavily 补充搜索（如果配置了 API Key）
            tavily_results = []
            if self.use_tavily and tavily_engine.enabled:
                try:
                    tavily_resp = await tavily_engine.search(topic, max_results=3)
                    tavily_results = [
                        {"title": r.title, "url": r.url, "snippet": r.content[:200]}
                        for r in tavily_resp.results
                    ]
                    self._log("tavily", f"Tavily 搜索完成 ({len(tavily_results)} 条)")
                except Exception as e:
                    logger.warning(f"Tavily 搜索失败: {e}")

            # 存储富化的文献信息（含 DOI、摘要）
            result["literature"] = [
                {
                    "title": p.title, "authors": p.authors, "year": p.year,
                    "citations": p.citation_count, "doi": p.doi,
                    "abstract": p.abstract[:200] if p.abstract else "",
                }
                for p in papers
            ] + [{"title": t["title"], "url": t["url"], "snippet": t["snippet"], "source": "tavily"} for t in tavily_results]
            refs = self._format_references(papers)
            if saved_count:
                self._log("literature", f"文献已保存到文献库 ({saved_count} 篇)")

            # 🔲 断点：分析+文献阶段完成，检查取消信号
            await _save_checkpoint("analysis")
            await self._check_cancelled()

            # 3️⃣ 建立模型
            self._log("modeler", "正在建立数学模型...")
            await self._publish("建模手正在建立数学模型...")
            self._update_progress("modeling", 0)

            # RAG 建模知识检索（为 Modeler 注入相关知识库参考）
            modeling_rag_context = ""
            if self.use_rag:
                try:
                    rag_modeling_docs = await rag_engine.search_for_modeling(problem_text, top_k=3)
                    if rag_modeling_docs:
                        modeling_rag_context = "\n\n## 相关知识库参考（建模方法）\n\n"
                        for doc in rag_modeling_docs:
                            modeling_rag_context += f"### {doc['title']}\n{doc['content'][:500]}\n\n"
                        self._log("rag", f"建模知识检索完成 ({len(rag_modeling_docs)} 篇参考)")
                except Exception as e:
                    logger.warning(f"RAG 建模检索失败: {e}")

            # 用户特殊要求（已在 _run_real 开头提取，此处直接使用）
            ref_context = f"\n\n参考文献：\n{refs}" if refs else ""
            model = await self._chat(
                self._get_llm("modeler"),
                prompts.modeler,
                f"请根据以下分析建立数学模型：\n\n{analysis}{ref_context}{modeling_rag_context}{notes_context}",
                max_tokens=TOKEN_BUDGET["modeling"],
            )
            result["model"] = {"content": model}
            self._update_progress("modeling", 100)

            # 📊 评估模型质量 (Shadow 模式)
            self._log("evaluator", "评估模型质量...")
            model_eval = self.evaluator.evaluator.evaluate_modeling(model)
            self._log("evaluator", f"模型评分: {model_eval.score}/100 {'✓' if model_eval.passed else '⚠️'}")

            # HIL: 建模阶段检查点
            hil_action = await self._hil_checkpoint(
                "modeling", "modeler",
                "数学模型已建立，是否继续生成代码？",
                model[:500],
            )
            if hil_action == "abort":
                result["status"] = "aborted"
                return result
            if hil_action == "regenerate":
                self._log("modeler", "用户要求重新建模")
                model = await self._chat(
                    self._get_llm("modeler"),
                    prompts.modeler,
                    f"请根据用户反馈重新建立数学模型：\n\n{analysis}\n\n用户反馈：请从不同角度重新建模",
                    max_tokens=TOKEN_BUDGET["retry"],
                )
                result["model"] = {"content": model}

            # 🔲 断点：建模阶段完成，检查取消信号
            await _save_checkpoint("modeling")
            await self._check_cancelled()

            # 4️⃣ 生成代码
            self._log("coder", "正在生成代码...")
            await self._publish("代码手正在生成代码...")
            self._update_progress("coding", 0)

            code_text = await self._chat(
                self._get_llm("coder"),
                prompts.coder.format(language=language) + notes_context,
                f"请根据以下模型生成{language}代码：\n\n{model}",
                max_tokens=TOKEN_BUDGET["coding"],
            )
            code = self._extract_code(code_text)
            result["code"] = {"language": language, "code": code}
            self._update_progress("coding", 50)

            # 5️⃣ 执行代码
            self._log("coder", "正在执行代码...")
            await self._publish("正在执行代码并验证结果...")
            exec_result = await self._execute_code(code, language)
            result["execution_result"] = {
                "success": exec_result.success,
                "output": exec_result.output[:2000],
                "error": exec_result.error[:500] if exec_result.error else "",
                "figures": exec_result.figures,
            }

            if exec_result.success:
                self._log("coder", "代码执行成功 ✓")
                await self._publish("代码执行成功 ✓")
            else:
                self._log("coder", f"代码执行失败: {exec_result.error[:100]}", "warning")
                await self._publish(f"代码执行遇到问题: {exec_result.error[:100]}", "warning")
            self._update_progress("coding", 100)

            # HIL: 代码执行阶段检查点
            exec_status = "成功" if exec_result.success else "失败"
            exec_output = exec_result.output[:300] if exec_result.output else "(无输出)"
            hil_action = await self._hil_checkpoint(
                "coding", "coder",
                f"代码执行{exec_status}，是否继续撰写论文？",
                f"执行结果: {exec_status}\n输出:\n{exec_output}",
            )
            if hil_action == "abort":
                result["status"] = "aborted"
                return result
            if hil_action == "regenerate":
                self._log("coder", "用户要求重新生成代码")
                code_text = await self._chat(
                    self._get_llm("coder"),
                    prompts.coder.format(language=language),
                    f"请根据用户反馈重新生成{language}代码：\n\n{model}\n\n请修复之前的问题并改进代码",
                    max_tokens=TOKEN_BUDGET["retry"],
                )
                code = self._extract_code(code_text)
                result["code"] = {"language": language, "code": code}
                exec_result = await self._execute_code(code, language)
                result["execution_result"] = {
                    "success": exec_result.success,
                    "output": exec_result.output[:2000],
                    "error": exec_result.error[:500] if exec_result.error else "",
                    "figures": exec_result.figures,
                }

            # 📊 评估代码质量
            self._log("evaluator", "评估代码质量...")
            code_eval = self.evaluator.evaluator.evaluate_coding(code, exec_result)
            self._log("evaluator", f"代码评分: {code_eval.score}/100 {'✓' if code_eval.passed else '⚠️'}")

            # 📈 图表管线 — 串联生成多个可视化图表
            chart_results = {}
            if self.config.get("chart_pipeline_enabled", True):
                chart_pipeline_config = self.config.get("chart_pipeline", [])
                # 回退：如果未配置，根据问题类型自动选择默认图表集
                if not chart_pipeline_config:
                    chart_pipeline_config = self._get_default_chart_pipeline(problem_text, analysis)
                    if chart_pipeline_config:
                        self._log("chart_pipeline", f"使用智能默认图表集（{len(chart_pipeline_config)} 个图表）")
                if chart_pipeline_config:
                    self._log("chart_pipeline", f"开始生成 {len(chart_pipeline_config)} 个图表...")
                    await self._publish(f"📈 图表管线：正在生成 {len(chart_pipeline_config)} 个可视化图表...")
                    self._update_progress("charting", 0)
                    chart_results = await self._run_chart_pipeline(
                        chart_pipeline_config,
                        problem_text=problem_text,
                        model=model,
                        analysis=analysis,
                        exec_result=exec_result,
                        language=language,
                    )
                    self._update_progress("charting", 100)
                    chart_count = len([c for c in chart_results.values() if c.get("success")])
                    self._log("chart_pipeline", f"图表生成完成: {chart_count}/{len(chart_pipeline_config)} 成功")
                    await self._publish(f"📈 图表管线完成: {chart_count} 个图表已生成")
                result["charts"] = chart_results

            # 🔲 断点：编程+图表阶段完成，检查取消信号
            await _save_checkpoint("coding")
            await self._check_cancelled()

            # 6️⃣ 撰写论文
            self._log("writer", "正在撰写论文...")
            await self._publish("论文手正在撰写论文...")
            self._update_progress("paper", 0)

            exec_summary = ""
            if exec_result.success and exec_result.output:
                exec_summary = f"\n\n代码执行结果：\n{exec_result.output[:500]}"

            # 将图表信息传递给 Writer（含文件名，确保论文中嵌入图片引用）
            chart_context = ""
            # 收集所有图表文件名（主代码 + 图表管线）
            all_chart_figures = list(result.get("execution_result", {}).get("figures", []))
            if chart_results:
                chart_items = []
                for chart_id, cr in chart_results.items():
                    if cr.get("success"):
                        exec_r = cr.get("execution_result", {})
                        chart_figs = exec_r.get("figures", []) if isinstance(exec_r, dict) else []
                        fig_names = [os.path.basename(f) for f in chart_figs if os.path.isfile(f)]
                        all_chart_figures.extend(chart_figs if isinstance(chart_figs, list) else [])
                        chart_items.append(
                            f"### {chart_id}\n"
                            f"图片文件: {', '.join(fig_names) if fig_names else '(图表已生成)'}\n"
                            f"```python\n{cr.get('code', '')[:200]}\n```"
                        )
                if chart_items:
                    # 关键：告诉 Writer 用 Markdown 图片语法嵌入
                    all_fig_names = [os.path.basename(f) for f in all_chart_figures if os.path.isfile(f)]
                    embed_instruction = ""
                    if all_fig_names:
                        embed_instruction = (
                            "\n\n**重要：请在论文正文相应位置使用以下 Markdown 图片语法嵌入可视化图表：**\n"
                            + "\n".join(f"![{name.split('.')[0]}]({name})" for name in all_fig_names)
                            + "\n（图片文件已生成在工作目录，直接使用文件名引用即可）\n"
                        )
                    chart_context = (
                        "\n\n## 已生成的可视化图表\n\n"
                        + embed_instruction
                        + "\n" + "\n\n".join(chart_items)
                    )

            paper = await self._chat(
                self._get_llm("writer"),
                prompts.writer + notes_context,
                f"请撰写完整的数学建模论文（不少于3000字，争取达到5000-8000字）：\n\n问题：{problem_text}\n\n模型：{model}{exec_summary}{chart_context}\n\n参考文献：\n{refs}" if refs else f"请撰写完整的数学建模论文（不少于3000字，争取达到5000-8000字）：\n\n问题：{problem_text}\n\n模型：{model}{exec_summary}{chart_context}",
                max_tokens=TOKEN_BUDGET["paper"],
            )
            result["paper"] = {"content": paper, "format": "markdown"}
            self._update_progress("paper", 100)

            # 📊 评估论文质量
            self._log("evaluator", "评估论文质量...")
            paper_eval = self.evaluator.evaluator.evaluate_paper(paper, problem_text)
            self._log("evaluator", f"论文评分: {paper_eval.score}/100 {'✓' if paper_eval.passed else '⚠️'}")
            if paper_eval.issues:
                for issue in paper_eval.issues[:3]:
                    self._log("evaluator", f"  [{issue['severity']}] {issue['message']}", "warning")
            result["_evaluation"] = {
                "analysis": {"score": analysis_eval.score, "passed": analysis_eval.passed},
                "modeling": {"score": model_eval.score, "passed": model_eval.passed},
                "coding": {"score": code_eval.score, "passed": code_eval.passed},
                "paper": {"score": paper_eval.score, "passed": paper_eval.passed},
            }

            # 📊 LLM 驱动的高级评估：代码-论文一致性 + 公式自洽性
            if exec_result.success and paper:
                try:
                    self._log("evaluator", "🔍 正在检查代码-论文一致性...")
                    consistency_eval = await self.evaluator.evaluator.evaluate_code_paper_consistency(
                        code=code,
                        code_output=exec_result.output[:3000] if exec_result.output else "",
                        paper_content=paper[:5000],
                        llm_chat=lambda sp, up: self._chat(
                            self._get_llm("coordinator"), sp, up,
                            max_tokens=2000, use_cache=False,
                        ),
                    )
                    self._log("evaluator", f"代码-论文一致性: {consistency_eval.score}/100 {'✓' if consistency_eval.passed else '⚠️'}")
                    if consistency_eval.issues:
                        for issue in consistency_eval.issues[:3]:
                            self._log("evaluator", f"  [{issue['severity']}] {issue['message']}", "warning")
                    result["_evaluation"]["code_paper_consistency"] = {
                        "score": consistency_eval.score,
                        "passed": consistency_eval.passed,
                        "issues": consistency_eval.issues[:5],
                    }
                except Exception as e:
                    logger.warning(f"代码-论文一致性检查异常: {e}")

                try:
                    self._log("evaluator", "🔍 正在检查公式自洽性...")
                    formula_eval = await self.evaluator.evaluator.evaluate_formula_consistency(
                        model_content=model,
                        llm_chat=lambda sp, up: self._chat(
                            self._get_llm("coordinator"), sp, up,
                            max_tokens=2000, use_cache=False,
                        ),
                    )
                    self._log("evaluator", f"公式自洽性: {formula_eval.score}/100 {'✓' if formula_eval.passed else '⚠️'}")
                    if formula_eval.issues:
                        for issue in formula_eval.issues[:3]:
                            self._log("evaluator", f"  [{issue['severity']}] {issue['message']}", "warning")
                    result["_evaluation"]["formula_consistency"] = {
                        "score": formula_eval.score,
                        "passed": formula_eval.passed,
                        "issues": formula_eval.issues[:5],
                    }
                except Exception as e:
                    logger.warning(f"公式自洽性检查异常: {e}")

            # HIL: 论文阶段检查点（最终确认）
            hil_action = await self._hil_checkpoint(
                "paper", "writer",
                "论文撰写完成，请确认最终结果。",
                paper[:500],
            )
            if hil_action == "regenerate":
                self._log("writer", "用户要求重新生成论文")
                paper = await self._chat(
                    self._get_llm("writer"),
                    prompts.writer,
                    f"请根据用户反馈重新撰写完整的数学建模论文：\n\n问题：{problem_text}\n\n模型：{model}{exec_summary}\n\n用户反馈：请改进论文质量，修正问题",
                    max_tokens=TOKEN_BUDGET["retry"],
                )
                result["paper"] = {"content": paper, "format": "markdown"}

            # 🔲 断点：论文阶段完成
            await _save_checkpoint("paper")

            # 聚合所有图片（主代码 + 图表管线）
            all_figures = list(result.get("execution_result", {}).get("figures", []))
            for chart_id, cr in chart_results.items():
                chart_figures = cr.get("execution_result", {}).get("figures", [])
                all_figures.extend(chart_figures)
            if all_figures:
                result["figures"] = all_figures

            return result

        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            await self._publish(f"工作流失败: {str(e)}", "error")
            raise


# ── 提示词 ────────────────────────────────────────────────

COORDINATOR_PROMPT = """你是数学建模协调器。你的职责是：
1. 理解问题背景和目标
2. 识别问题类型（优化/预测/评价/分类等）
3. 提取关键变量和约束
4. 建议合适的建模方法
5. 制定工作计划

输出结构化分析，使用中文。"""

MODELER_PROMPT = """你是数学建模专家。你的职责是：
1. 根据协调器的分析选择合适的数学模型
2. 建立数学公式（使用 LaTeX 格式）
3. 明确变量定义、约束条件、目标函数
4. 说明模型的优缺点和适用条件

输出完整的数学模型描述，使用中文。"""

CODER_PROMPT = """你是{language}编程专家。你的职责是：
1. 根据数学模型编写可执行的{language}代码
2. 代码必须完整可运行，包含所有必要的 import
3. 添加中文注释说明每一步
4. 输出结果并生成可视化图表（如果适用）
5. 保存图表到当前目录（matplotlib savefig）

只返回代码块，不要解释。"""

WRITER_PROMPT = """你是数学建模论文写作专家。你的职责是：
1. 按照标准数学建模论文格式撰写
2. 包含：摘要、问题重述、模型假设、符号说明、模型建立、模型求解、结果分析、模型评价、参考文献
3. 使用 Markdown 格式
4. 公式使用 LaTeX 格式
5. 图表有编号和标题
6. 参考文献格式规范

输出完整论文，使用中文。"""
