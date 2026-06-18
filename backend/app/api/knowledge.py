"""知识库 + 竞赛日历 + 论文验收 API"""

import os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from app.core.engine.knowledge import knowledge_base
from app.core.engine.competitions import competition_calendar
from app.core.engine.validator import paper_validator
from app.core.engine.typst_compiler import typst_compiler
from app.core.engine.web_search import unified_search
from app.core.engine.hil import hil_manager
from app.core.engine.papers import paper_database
from app.core.engine.rag import rag_engine
from app.core.engine.evaluator import PhaseEvaluator, FeedbackRunner, EvalMode
from app.core.engine.handoff import handoff_manager, retry_handler
from app.core.engine.tavily_search import tavily_engine
from app.core.engine.i18n import i18n
from app.core.engine.interpreter import LocalInterpreter
from app.core.engine.literature import LiteratureSearch, Paper
from app.models.database import LiteratureDB, SessionLocal

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


# ── 知识库 ────────────────────────────────────────────────

@router.get("/knowledge/models")
async def get_all_models():
    """获取所有建模方法"""
    return {"models": knowledge_base.get_all_models()}


@router.get("/knowledge/models/{model_id}")
async def get_model(model_id: str):
    """获取模型详情"""
    model = knowledge_base.get_model(model_id)
    if not model:
        raise HTTPException(404, f"模型 {model_id} 不存在")
    return model


@router.get("/knowledge/models/category/{category}")
async def get_models_by_category(category: str):
    """按类别获取模型"""
    return {"models": knowledge_base.get_models_by_category(category)}


@router.get("/knowledge/decision-tree")
async def get_decision_tree():
    """获取模型选择决策树"""
    return knowledge_base.get_decision_tree()


class RecommendRequest(BaseModel):
    problem_type: Optional[str] = ""
    keywords: Optional[List[str]] = None

    def model_post_init(self, __context):
        if self.keywords is None:
            self.keywords = []

@router.post("/knowledge/recommend")
async def recommend_models(req: RecommendRequest):
    """推荐模型"""
    return {"recommendations": knowledge_base.recommend(req.problem_type, req.keywords)}


# ── 竞赛日历 ──────────────────────────────────────────────

@router.get("/competitions")
async def get_competitions():
    """获取所有竞赛"""
    return {"competitions": competition_calendar.get_all()}


@router.get("/competitions/{comp_id}")
async def get_competition(comp_id: str):
    """获取竞赛详情"""
    comp = competition_calendar.get_competition(comp_id)
    if not comp:
        raise HTTPException(404, f"竞赛 {comp_id} 不存在")
    return comp


@router.get("/competitions/upcoming/list")
async def get_upcoming_competitions():
    """获取即将开始的竞赛"""
    return {"competitions": competition_calendar.get_upcoming()}


# ── 论文验收 ──────────────────────────────────────────────

class ValidateRequest(BaseModel):
    content: str
    problem_text: Optional[str] = ""

@router.post("/validate/paper")
async def validate_paper(req: ValidateRequest):
    """验收论文"""
    report = paper_validator.validate(req.content, req.problem_text)
    return {
        "score": report.total_score,
        "summary": report.summary,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "issues": [
            {
                "severity": i.severity,
                "category": i.category,
                "message": i.message,
                "location": i.location,
                "suggestion": i.suggestion,
            }
            for i in report.issues
        ],
    }


# ── 费用预估 ──────────────────────────────────────────────

# 各模型每 1K token 价格（美元）
MODEL_PRICING = {
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-coder": {"input": 0.00014, "output": 0.00028},
    "deepseek-v4-flash": {"input": 0.00007, "output": 0.00014},
    "deepseek-v4-pro": {"input": 0.00028, "output": 0.00056},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
}

# 每个阶段预估 token 用量
PHASE_TOKEN_ESTIMATE = {
    "analysis": {"input": 2000, "output": 1500},
    "modeling": {"input": 3000, "output": 2500},
    "coding": {"input": 3000, "output": 3000},
    "paper": {"input": 4000, "output": 5000},
    "literature": {"input": 500, "output": 200},
}


class EstimateRequest(BaseModel):
    model: str = "deepseek-chat"
    phases: Optional[List[str]] = None  # 默认全部阶段


@router.post("/estimate/cost")
async def estimate_cost(req: EstimateRequest):
    """预估 API 费用"""
    pricing = MODEL_PRICING.get(req.model, MODEL_PRICING["deepseek-chat"])
    phases = req.phases or list(PHASE_TOKEN_ESTIMATE.keys())

    total_input = 0
    total_output = 0
    breakdown = {}

    for phase in phases:
        est = PHASE_TOKEN_ESTIMATE.get(phase, {"input": 1000, "output": 1000})
        input_cost = (est["input"] / 1000) * pricing["input"]
        output_cost = (est["output"] / 1000) * pricing["output"]
        total_input += est["input"]
        total_output += est["output"]
        breakdown[phase] = {
            "input_tokens": est["input"],
            "output_tokens": est["output"],
            "cost_usd": round(input_cost + output_cost, 6),
        }

    total_cost = (total_input / 1000) * pricing["input"] + (total_output / 1000) * pricing["output"]

    return {
        "model": req.model,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": round(total_cost, 6),
        "total_cost_cny": round(total_cost * 7.2, 4),
        "breakdown": breakdown,
    }


# ── Typst 编译 ────────────────────────────────────────────

@router.get("/typst/templates")
async def get_typst_templates():
    """获取可用 Typst 模板"""
    return {"templates": typst_compiler.get_templates()}


class CompileRequest(BaseModel):
    content: str
    template_id: str = "cumcm"
    title: str = "数学建模论文"


@router.post("/typst/compile")
async def compile_paper(req: CompileRequest):
    """编译论文为 PDF"""
    result = typst_compiler.compile(
        content=req.content,
        template_id=req.template_id,
        title=req.title,
    )
    return result


# ── Web 搜索 ──────────────────────────────────────────────

@router.get("/search")
async def web_search(q: str, max_results: int = 5):
    """统一搜索（网页 + 学术论文）"""
    return await unified_search.search_all(q, max_results)


# ── HIL 人机协作 ──────────────────────────────────────────

@router.get("/hil/pending")
async def get_hil_pending():
    """获取待决策的检查点"""
    return {"checkpoints": hil_manager.get_pending()}


@router.get("/hil/resolved")
async def get_hil_resolved():
    """获取已决策的检查点"""
    return {"checkpoints": hil_manager.get_resolved()}


class HILDecision(BaseModel):
    action: str
    user_input: Optional[str] = None


@router.post("/hil/decide/{cp_id}")
async def hil_decide(cp_id: str, decision: HILDecision):
    """用户做出决策"""
    success = hil_manager.resolve(cp_id, decision.action, decision.user_input)
    if not success:
        raise HTTPException(404, f"检查点 {cp_id} 不存在")
    return {"success": True, "action": decision.action}


# ── 获奖论文数据 ──────────────────────────────────────────

@router.get("/papers/patterns")
async def get_paper_patterns(competition: str = None, award: str = None):
    """获取获奖论文模式"""
    return {"patterns": paper_database.get_patterns(competition, award)}


@router.get("/papers/mistakes")
async def get_common_mistakes(competition: str = "CUMCM"):
    """获取常见易错点"""
    return {"competition": competition, "mistakes": paper_database.get_mistakes(competition)}


@router.get("/papers/guidelines")
async def get_writing_guidelines():
    """获取写作规范"""
    return {"guidelines": paper_database.get_guidelines()}


# ── RAG 知识库检索 ──────────────────────────────────────────

async def init_rag_engine():
    """初始化 RAG 引擎（由 lifespan 调用）"""
    try:
        await rag_engine.initialize()
    except Exception as e:
        import logging
        logging.warning(f"RAG 初始化失败: {e}")


class RAGSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    top_k: int = 5


@router.post("/rag/search")
async def rag_search(req: RAGSearchRequest):
    """RAG 知识库检索"""
    results = await rag_engine.search(
        query=req.query,
        category=req.category,
        top_k=req.top_k,
    )
    return {
        "query": req.query,
        "results": [
            {
                "title": doc.title,
                "content": doc.content[:500],
                "score": round(score, 4),
                "category": doc.category,
                "tags": doc.tags,
            }
            for doc, score in results
        ],
    }


@router.get("/rag/stats")
async def rag_stats():
    """RAG 知识库统计"""
    return rag_engine.get_stats()


# ── 论文评估 ────────────────────────────────────────────────


class EvaluateRequest(BaseModel):
    content: str
    phase: str = "paper"  # analysis/modeling/coding/paper
    problem_text: Optional[str] = ""


@router.post("/evaluate")
async def evaluate_content(req: EvaluateRequest):
    """评估内容质量"""
    evaluator = PhaseEvaluator()

    if req.phase == "analysis":
        result = evaluator.evaluate_analysis(req.content, req.problem_text)
    elif req.phase == "modeling":
        result = evaluator.evaluate_modeling(req.content)
    elif req.phase == "coding":
        result = evaluator.evaluate_coding(req.content)
    elif req.phase == "paper":
        result = evaluator.evaluate_paper(req.content, req.problem_text)
    else:
        raise HTTPException(400, f"不支持的阶段: {req.phase}")

    return {
        "phase": result.phase,
        "score": result.score,
        "passed": result.passed,
        "issues": result.issues,
        "suggestions": result.suggestions,
        "summary": result.summary,
    }


# ── A2A Handoff ─────────────────────────────────────────────


@router.get("/handoff/history")
async def get_handoff_history():
    """获取模型切换历史"""
    return {"history": handoff_manager.get_history()}


@router.get("/handoff/stats")
async def get_handoff_stats():
    """获取 Handoff 统计"""
    return handoff_manager.get_stats()


@router.post("/handoff/register")
async def register_model(
    name: str,
    api_key: str,
    base_url: str = "",
    model_id: str = "",
    api_type: str = "openai",
    priority: int = 0,
):
    """注册备用模型"""
    from app.core.engine.handoff import ModelConfig
    handoff_manager.register_model(ModelConfig(
        name=name, api_key=api_key, base_url=base_url,
        model_id=model_id, api_type=api_type, priority=priority,
    ))
    return {"message": f"模型 {name} 已注册", "total_models": len(handoff_manager.models)}


# ── Tavily Web Search ───────────────────────────────────────


@router.get("/tavily/search")
async def tavily_search(
    q: str,
    max_results: int = 5,
    search_depth: str = "basic",
):
    """Tavily 联网搜索"""
    response = await tavily_engine.search(
        query=q,
        search_depth=search_depth,
        max_results=max_results,
        include_answer=True,
    )
    return {
        "query": response.query,
        "answer": response.answer,
        "results": [
            {"title": r.title, "url": r.url, "content": r.content[:500], "score": r.score}
            for r in response.results
        ],
        "images": response.images,
        "response_time": response.response_time,
    }


@router.get("/tavily/academic")
async def tavily_academic(topic: str, max_results: int = 5):
    """Tavily 学术搜索"""
    results = await tavily_engine.search_academic(topic, max_results)
    return {"topic": topic, "results": results}


@router.get("/tavily/data")
async def tavily_data(query: str, max_results: int = 5):
    """Tavily 数据搜索"""
    results = await tavily_engine.search_data(query, max_results)
    return {"query": query, "results": results}


# ── 国际化 / English Support ────────────────────────────────


@router.get("/i18n/languages")
async def get_supported_languages():
    """获取支持的语言列表"""
    return {"languages": i18n.get_supported_languages()}


@router.get("/i18n/prompts")
async def get_prompts(language: str = "zh"):
    """获取提示词"""
    prompts = i18n.get_prompts(language)
    return {
        "language": language,
        "coordinator": prompts.coordinator,
        "modeler": prompts.modeler,
        "coder": prompts.coder,
        "writer": prompts.writer,
    }


@router.get("/i18n/template")
async def get_paper_template(language: str = "zh"):
    """获取论文模板"""
    return {
        "language": language,
        "template": i18n.get_paper_template(language),
    }


# ── 代码解释器状态 ──────────────────────────────────────────


@router.get("/interpreter/languages")
async def get_available_languages():
    """获取可用的代码解释器语言"""
    interpreter = LocalInterpreter()
    return {
        "available": interpreter.available_languages,
        "details": {
            "python": interpreter.is_language_available("python"),
            "r": interpreter.is_language_available("r"),
            "matlab": interpreter.is_language_available("matlab"),
            "julia": interpreter.is_language_available("julia"),
        }
    }


# ── 文献管理 ──────────────────────────────────────────────


@router.get("/literature/search")
async def literature_search(
    q: str,
    limit: int = 10,
    task_id: str = None,
    save: bool = True,
    source: str = "cnki",
):
    """搜索文献并可选保存到独立文献表

    Args:
        source: 数据源（"cnki" 或 "openalex"），默认 "cnki"（中国可用）。
    """
    searcher = LiteratureSearch()
    papers = await searcher.search(q, limit, source=source)

    if save and papers:
        db = SessionLocal()
        try:
            searcher.set_db_session(db)
            await searcher._save_to_db(papers, q, task_id)
        finally:
            db.close()

    return {
        "query": q,
        "count": len(papers),
        "results": [
            {
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "doi": p.doi,
                "journal": p.journal,
                "abstract": p.abstract[:300] if p.abstract else "",
                "citation_count": p.citation_count,
                "source": p.source,
            }
            for p in papers
        ],
    }


@router.get("/literature/history")
async def literature_history(
    task_id: str = None,
    limit: int = 50,
):
    """获取文献搜索历史"""
    db = SessionLocal()
    try:
        q = db.query(LiteratureDB)
        if task_id:
            q = q.filter(LiteratureDB.task_id == task_id)
        q = q.order_by(LiteratureDB.created_at.desc()).limit(limit)
        entries = q.all()
        return {
            "count": len(entries),
            "results": [
                {
                    "id": e.id,
                    "title": e.title,
                    "authors": e.authors,
                    "year": e.year,
                    "doi": e.doi,
                    "journal": e.journal,
                    "citation_count": e.citation_count,
                    "search_query": e.search_query,
                    "task_id": e.task_id,
                    "created_at": e.created_at.isoformat() if e.created_at else "",
                }
                for e in entries
            ],
        }
    finally:
        db.close()


@router.get("/literature/export/{task_id}")
async def literature_export(
    task_id: str,
    format: str = "bibtex",  # bibtex / reference / both
):
    """导出任务关联的文献（BibTeX / 参考文献列表）"""
    db = SessionLocal()
    try:
        entries = db.query(LiteratureDB).filter(
            LiteratureDB.task_id == task_id
        ).order_by(LiteratureDB.citation_count.desc()).all()

        if not entries:
            raise HTTPException(404, f"任务 {task_id} 没有关联文献")

        papers = [
            {
                "title": e.title,
                "authors": e.authors,
                "year": e.year,
                "doi": e.doi,
                "url": e.url,
                "journal": e.journal,
                "citation_count": e.citation_count,
            }
            for e in entries
        ]

        result = {"task_id": task_id, "count": len(papers)}
        if format in ("bibtex", "both"):
            result["bibtex"] = LiteratureSearch.export_bibtex(papers)
        if format in ("reference", "both"):
            result["reference_list"] = LiteratureSearch.export_reference_list(papers)

        return result
    finally:
        db.close()


@router.get("/literature/stats")
async def literature_stats():
    """文献库统计"""
    db = SessionLocal()
    try:
        total = db.query(LiteratureDB).count()
        sources = {}
        from sqlalchemy import func
        rows = db.query(
            LiteratureDB.source, func.count(LiteratureDB.id)
        ).group_by(LiteratureDB.source).all()
        sources = {r[0]: r[1] for r in rows}

        return {
            "total_literature": total,
            "by_source": sources,
        }
    finally:
        db.close()
