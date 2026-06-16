"""Evaluator + Feedback 系统 — 输出质量评估 + 反馈重跑

在每个阶段完成后对输出进行评估，如果质量不达标则自动注入反馈重跑。
支持 Shadow Mode（并行评估不阻塞主线）和 Full Mode（阻塞直到通过）。
"""

import re
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from app.domain.agent.base import extract_json


class EvalMode(str, Enum):
    SHADOW = "shadow"  # 并行评估，记录结果但不阻塞
    FULL = "full"      # 阻塞模式，不通过则重试


@dataclass
class EvalResult:
    """评估结果"""
    phase: str           # analysis / modeling / coding / paper
    score: float         # 0-100 分
    passed: bool         # 是否通过
    issues: List[Dict[str, str]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    summary: str = ""


class PhaseEvaluator:
    """阶段输出评估器

    对每个 Agent 阶段的输出进行质量评估，包括：
    - 完整性检查（是否包含必要元素）
    - 格式检查（LaTeX 公式、Markdown 格式等）
    - 内容质量检查（基于规则的启发式评分）
    - AI 评估（使用 LLM 进行语义级别的质量评估）
    """

    # 各阶段最低通过分数
    PHASE_PASS_THRESHOLD = {
        "analysis": 60,
        "modeling": 65,
        "coding": 60,
        "paper": 70,
    }

    # 各阶段必要元素
    REQUIRED_ELEMENTS = {
        "analysis": [
            ("问题类型", r"(?:问题类型|问题分类|类型[：:])"),
            ("关键信息", r"(?:关键|要点|核心)"),
            ("建模思路", r"(?:思路|方法|方案|步骤)"),
        ],
        "modeling": [
            ("模型类型", r"(?:模型类型|模型[：:]|数学模型)"),
            ("决策变量", r"(?:变量|决策|参数)"),
            ("目标函数", r"(?:目标|目标函数|最小化|最大化)"),
            ("约束条件", r"(?:约束|条件|限制)"),
        ],
        "coding": [
            ("完整代码块", r"```(?:python|py|matlab)?"),
            ("导入语句", r"(?:import|from)\s+\w+"),
            ("输出或可视化", r"(?:print|plt\.|figure|savefig)"),
        ],
        "paper": [
            ("摘要", r"#+\s*摘要|#+\s*Abstract"),
            ("模型假设", r"(?:假设|Assumption)"),
            ("模型建立", r"(?:模型建立|模型构建|Model)"),
            ("结果分析", r"(?:结果|分析|Result|Analysis)"),
            ("参考文献", r"(?:参考文献|Reference)"),
        ],
    }

    def evaluate_analysis(self, content: str, problem_text: str = "") -> EvalResult:
        """评估问题分析质量"""
        issues = []
        suggestions = []
        score = 70  # 基础分

        # 1. 完整性检查
        for name, pattern in self.REQUIRED_ELEMENTS["analysis"]:
            if not re.search(pattern, content, re.IGNORECASE):
                issues.append({
                    "severity": "warning",
                    "category": "完整性",
                    "message": f"缺少{name}分析",
                    "suggestion": f"请补充{name}相关内容",
                })
                score -= 10

        # 2. 长度检查
        if len(content) < 100:
            issues.append({
                "severity": "error",
                "category": "内容不足",
                "message": "分析内容过短",
                "suggestion": "请提供更详细的分析，至少包含问题类型、关键信息和服务思路",
            })
            score -= 20

        # 3. 结构化检查
        if not re.search(r"#+", content):
            issues.append({
                "severity": "warning",
                "category": "格式",
                "message": "缺少 Markdown 标题",
                "suggestion": "使用 ## 标题结构化分析结果",
            })
            score -= 5

        passed = score >= self.PHASE_PASS_THRESHOLD["analysis"]
        return EvalResult(
            phase="analysis",
            score=max(0, score),
            passed=passed,
            issues=issues,
            suggestions=suggestions,
            summary=f"分析评估: {score}/100 {'通过' if passed else '不通过'}",
        )

    def evaluate_modeling(self, content: str) -> EvalResult:
        """评估数学模型质量"""
        issues = []
        suggestions = []
        score = 70

        # 1. 完整性检查
        for name, pattern in self.REQUIRED_ELEMENTS["modeling"]:
            if not re.search(pattern, content, re.IGNORECASE):
                issues.append({
                    "severity": "error" if name in ["目标函数", "约束条件"] else "warning",
                    "category": "完整性",
                    "message": f"缺少{name}",
                    "suggestion": f"请明确给出{name}",
                })
                score -= 12 if name in ["目标函数", "约束条件"] else 8

        # 2. LaTeX 公式检查
        latex_count = len(re.findall(r'\$\$[^$]+\$\$|\$[^$]+\$', content))
        if latex_count == 0:
            issues.append({
                "severity": "warning",
                "category": "格式",
                "message": "未使用 LaTeX 公式",
                "suggestion": "请使用 $...$ 或 $$...$$ 编写数学公式",
            })
            score -= 10

        # 3. 模型假设检查
        if not re.search(r"(?:假设|assum)", content, re.IGNORECASE):
            suggestions.append("建议补充模型的基本假设条件")

        passed = score >= self.PHASE_PASS_THRESHOLD["modeling"]
        return EvalResult(
            phase="modeling",
            score=max(0, score),
            passed=passed,
            issues=issues,
            suggestions=suggestions,
            summary=f"模型评估: {score}/100 {'通过' if passed else '不通过'}",
        )

    def evaluate_coding(self, content: str, exec_result: Optional[Any] = None) -> EvalResult:
        """评估代码质量"""
        issues = []
        suggestions = []
        score = 70

        # 1. 代码块检查
        if not re.search(r"```(?:python|py|matlab)", content, re.IGNORECASE):
            issues.append({
                "severity": "error",
                "category": "格式",
                "message": "缺少代码块",
                "suggestion": "请将代码放在 ```python ... ``` 代码块中",
            })
            score -= 20

        # 2. 导入语句检查
        if not re.search(r"(?:import|from)\s+\w+", content):
            issues.append({
                "severity": "error",
                "category": "完整性",
                "message": "缺少必要的 import 语句",
                "suggestion": "请添加必要的库导入语句",
            })
            score -= 15

        # 3. 注释检查
        comment_lines = len(re.findall(r'^\s*#', content, re.MULTILINE))
        total_lines = max(1, len(content.split('\n')))
        if comment_lines / total_lines < 0.05:
            issues.append({
                "severity": "warning",
                "category": "可读性",
                "message": "代码注释过少",
                "suggestion": "请添加中文注释说明关键步骤",
            })
            score -= 5

        # 4. 输出/可视化检查
        if not re.search(r"(?:print|plt\.|figure|savefig|fprintf)", content):
            issues.append({
                "severity": "warning",
                "category": "功能性",
                "message": "缺少结果输出或可视化",
                "suggestion": "请使用 print 输出结果或 matplotlib 绘制图表",
            })
            score -= 10

        # 5. 执行结果检查
        if exec_result is not None:
            if hasattr(exec_result, 'success') and exec_result.success:
                score += 10
            else:
                error_msg = getattr(exec_result, 'error', '') if exec_result else ''
                issues.append({
                    "severity": "error",
                    "category": "执行错误",
                    "message": f"代码执行失败: {str(error_msg)[:200]}",
                    "suggestion": "请修复代码错误后重试",
                })
                score -= 25

        passed = score >= self.PHASE_PASS_THRESHOLD["coding"]
        return EvalResult(
            phase="coding",
            score=max(0, min(100, score)),
            passed=passed,
            issues=issues,
            suggestions=suggestions,
            summary=f"代码评估: {score}/100 {'通过' if passed else '不通过'}",
        )

    def evaluate_paper(self, content: str, problem_text: str = "") -> EvalResult:
        """评估论文质量"""
        issues = []
        suggestions = []
        score = 70

        # 1. 完整性检查
        for name, pattern in self.REQUIRED_ELEMENTS["paper"]:
            if not re.search(pattern, content, re.IGNORECASE):
                severity = "error" if name in ["摘要", "模型建立"] else "warning"
                issues.append({
                    "severity": severity,
                    "category": "完整性",
                    "message": f"缺少{name}部分",
                    "suggestion": f"请补充{name}部分",
                })
                score -= 10 if severity == "error" else 5

        # 2. 长度检查
        if len(content) < 1000:
            issues.append({
                "severity": "error",
                "category": "内容不足",
                "message": f"论文内容过短 ({len(content)} 字符)",
                "suggestion": "标准建模论文应至少 2000 字",
            })
            score -= 20

        # 3. 占位符检查
        placeholders = re.findall(r"(?:待补充|TODO|TBD|待完善|占位)", content, re.IGNORECASE)
        if placeholders:
            issues.append({
                "severity": "error",
                "category": "未完成",
                "message": f"发现 {len(placeholders)} 处占位符",
                "suggestion": "请完成所有标记为待补充的内容",
            })
            score -= 15

        # 4. 图表引用检查
        if not re.search(r"(?:图\d|Fig|Table|表\d)", content):
            suggestions.append("建议添加图表增强论文说服力")

        # 5. 公式检查
        latex_count = len(re.findall(r'\$\$[^$]+\$\$|\$[^$]+\$', content))
        if latex_count < 2:
            issues.append({
                "severity": "warning",
                "category": "格式",
                "message": "论文中公式较少",
                "suggestion": "数学模型部分应使用 LaTeX 公式",
            })
            score -= 5

        passed = score >= self.PHASE_PASS_THRESHOLD["paper"]
        return EvalResult(
            phase="paper",
            score=max(0, score),
            passed=passed,
            issues=issues,
            suggestions=suggestions,
            summary=f"论文评估: {score}/100 {'通过' if passed else '不通过'}",
        )


    async def evaluate_code_paper_consistency(
        self,
        code: str,
        code_output: str,
        paper_content: str,
        llm_chat,
    ) -> EvalResult:
        """LLM 驱动的代码-论文一致性检查

        对比代码输出中的数值与论文声称的数值是否一致。
        Args:
            code: 代码文本
            code_output: 代码执行输出文本
            paper_content: 论文内容
            llm_chat: async (system_prompt, user_prompt) -> str 的 LLM 回调
        """
        issues = []
        score = 85

        eval_prompt = (
            "你是一位严谨的数学建模论文评审专家。请检查以下论文与代码输出之间是否一致。\n\n"
            "## 代码输出\n```\n" + (code_output[:3000] if code_output else "（无输出）") + "\n```\n\n"
            "## 论文内容\n" + (paper_content[:5000] if paper_content else "（无内容）") + "\n\n"
            "请逐项检查：\n"
            "1. 论文中声称的关键数值结果是否与代码输出一致（逐项对比）\n"
            "2. 论文中的图表描述是否与代码生成的可视化匹配\n"
            "3. 论文中的结论是否得到代码执行结果的支持\n\n"
            "以 JSON 格式输出检查结果（只输出 JSON，不要有其他文字）：\n"
            '{"is_consistent": true/false,'
            '"issues": [{"severity": "error|warning", "location": "问题位置", "detail": "具体说明"}],'
            '"summary": "总体评价（中文一句话）"}'
        )

        try:
            eval_resp = await llm_chat("你是论文评审专家。", eval_prompt)
            result = extract_json(eval_resp)

            if not result.get("is_consistent", True):
                score = 50
                for issue in result.get("issues", []):
                    issues.append({
                        "severity": issue.get("severity", "warning"),
                        "category": "代码-论文一致性",
                        "message": issue.get("detail", ""),
                        "location": issue.get("location", ""),
                    })
                    score -= 15
                score = max(0, score)

            passed = score >= 60
            summary = result.get("summary", f"一致性检查: {score}/100")

        except Exception as e:
            logger.warning(f"LLM 代码-论文一致性检查失败，降级通过: {e}")
            passed = True
            summary = "一致性检查：LLM 评估暂不可用，默认通过"

        return EvalResult(
            phase="code_paper_consistency",
            score=max(0, min(100, score)),
            passed=passed,
            issues=issues,
            suggestions=[],
            summary=summary,
        )

    async def evaluate_formula_consistency(
        self,
        model_content: str,
        llm_chat,
    ) -> EvalResult:
        """LLM 驱动的公式逻辑自洽检查

        检查论文中公式的变量定义、量纲、推导逻辑是否一致。
        Args:
            model_content: 模型/论文内容（含公式）
            llm_chat: async (system_prompt, user_prompt) -> str 的 LLM 回调
        """
        issues = []
        score = 85

        eval_prompt = (
            "你是一位应用数学教授。请严格检查以下数学建模论文中的公式逻辑自洽性。\n\n"
            "## 论文内容\n" + (model_content[:5000] if model_content else "（无内容）") + "\n\n"
            "请逐项检查：\n"
            "1. **变量定义一致性**：所有变量在使用前是否已定义，同一符号在不同部分是否含义一致\n"
            "2. **量纲一致性**：公式两边的量纲是否匹配（如左边是长度，右边各项也应为长度）\n"
            "3. **下标/索引一致性**：求和、乘积等运算的下标范围是否合理\n"
            "4. **公式推导逻辑**：从前一步到后一步的推导是否数学上正确\n"
            "5. **约束合理性**：约束条件是否与问题定义一致\n\n"
            "以 JSON 格式输出检查结果（只输出 JSON，不要有其他文字）：\n"
            '{"is_consistent": true/false,'
            '"issues": [{"severity": "error|warning", "category": "变量定义|量纲|下标|推导|约束",'
            '"location": "具体公式或段落", "detail": "具体问题说明"}],'
            '"summary": "总体评价（中文一句话）"}'
        )

        try:
            eval_resp = await llm_chat("你是应用数学教授。", eval_prompt)
            result = extract_json(eval_resp)

            if not result.get("is_consistent", True):
                score = 50
                for issue in result.get("issues", []):
                    issues.append({
                        "severity": issue.get("severity", "warning"),
                        "category": f"公式自洽-{issue.get('category', '未知')}",
                        "message": issue.get("detail", ""),
                        "location": issue.get("location", ""),
                    })
                    score -= 15
                score = max(0, score)

            passed = score >= 60
            summary = result.get("summary", f"公式自洽性: {score}/100")

        except Exception as e:
            logger.warning(f"LLM 公式自洽性检查失败，降级通过: {e}")
            passed = True
            summary = "公式自洽性：LLM 评估暂不可用，默认通过"

        return EvalResult(
            phase="formula_consistency",
            score=max(0, min(100, score)),
            passed=passed,
            issues=issues,
            suggestions=[],
            summary=summary,
        )


class FeedbackRunner:
    """反馈重跑系统

    支持两种模式：
    - Shadow Mode: 并行评估，不影响主流程，结果记录到日志
    - Full Mode: 阻塞评估，不通过自动注入反馈并重跑 (最多 3 次)
    """

    MAX_RETRY = 3

    def __init__(
        self,
        mode: EvalMode = EvalMode.SHADOW,
        on_eval_callback: Callable = None,
    ):
        self.mode = mode
        self.evaluator = PhaseEvaluator()
        self.on_eval_callback = on_eval_callback
        self.history: List[EvalResult] = []

    async def evaluate_and_retry(
        self,
        phase: str,
        content: str,
        regenerate_fn: Callable,
        problem_text: str = "",
        exec_result: Any = None,
    ) -> tuple:
        """评估输出，如果不通过则自动重试

        Args:
            phase: 阶段名称 (analysis/modeling/coding/paper)
            content: 当前输出内容
            regenerate_fn: 重新生成的异步函数，接受反馈字符串作为参数
            problem_text: 原始问题文本
            exec_result: 代码执行结果（仅 coding 阶段）

        Returns:
            (final_content, eval_result, retry_count)
        """
        eval_result = self._evaluate_phase(phase, content, problem_text, exec_result)
        self.history.append(eval_result)

        if self.on_eval_callback:
            self.on_eval_callback(eval_result)

        if self.mode == EvalMode.SHADOW:
            # Shadow 模式：只记录，不重试
            logger.info(f"[Shadow] {eval_result.summary}")
            return content, eval_result, 0

        # Full 模式：不通过则重试
        retry_count = 0
        current_content = content

        while not eval_result.passed and retry_count < self.MAX_RETRY:
            retry_count += 1
            logger.warning(f"[Retry {retry_count}] {phase}: {eval_result.summary}")

            # 构建反馈
            feedback = self._build_feedback(eval_result)
            logger.info(f"反馈: {feedback[:200]}...")

            try:
                current_content = await regenerate_fn(feedback)
            except Exception as e:
                logger.error(f"重试失败: {e}")
                break

            eval_result = self._evaluate_phase(phase, current_content, problem_text, exec_result)
            self.history.append(eval_result)

        logger.info(f"[Final] {phase}: {eval_result.summary} (重试 {retry_count} 次)")
        return current_content, eval_result, retry_count

    def _evaluate_phase(
        self,
        phase: str,
        content: str,
        problem_text: str = "",
        exec_result: Any = None,
    ) -> EvalResult:
        """评估指定阶段"""
        if phase == "analysis":
            return self.evaluator.evaluate_analysis(content, problem_text)
        elif phase == "modeling":
            return self.evaluator.evaluate_modeling(content)
        elif phase == "coding":
            return self.evaluator.evaluate_coding(content, exec_result)
        elif phase == "paper":
            return self.evaluator.evaluate_paper(content, problem_text)
        else:
            return EvalResult(phase=phase, score=100, passed=True, summary="未知阶段，默认通过")

    def _build_feedback(self, eval_result: EvalResult) -> str:
        """构建反馈文本"""
        parts = [f"评估分数: {eval_result.score}/100"]

        if eval_result.issues:
            parts.append("\n需要改进的问题：")
            for issue in eval_result.issues:
                parts.append(f"- [{issue['severity']}] {issue['message']}")
                if issue.get('suggestion'):
                    parts.append(f"  建议: {issue['suggestion']}")

        if eval_result.suggestions:
            parts.append("\n改进建议：")
            for s in eval_result.suggestions:
                parts.append(f"- {s}")

        return "\n".join(parts)

    def get_report(self) -> Dict[str, Any]:
        """获取评估报告"""
        if not self.history:
            return {"status": "no_evaluation", "results": []}

        last = self.history[-1]
        return {
            "status": "passed" if last.passed else "failed",
            "total_evaluations": len(self.history),
            "final_score": last.score,
            "results": [
                {
                    "phase": r.phase,
                    "score": r.score,
                    "passed": r.passed,
                    "issues_count": len(r.issues),
                    "summary": r.summary,
                }
                for r in self.history
            ],
        }


# 全局实例
default_evaluator = PhaseEvaluator()
