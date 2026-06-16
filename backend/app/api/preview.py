"""预览 API"""

from app._paths import PROJECT_ROOT

import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
router = APIRouter()


def _get_task(task_id: str) -> dict:
    """从 SQLite 数据库获取任务"""
    from app.models.database import TaskDB, SessionLocal
    from app.api.tasks import _task_to_dict

    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return _task_to_dict(task)
    finally:
        db.close()


@router.get("/preview/{task_id}/paper")
async def preview_paper(task_id: str):
    """预览论文 PDF"""
    # 尝试从项目目录查找 PDF
    base_dir = PROJECT_ROOT
    paper_path = os.path.join(base_dir, "project", task_id, "paper.pdf")

    if os.path.exists(paper_path):
        return FileResponse(paper_path, media_type="application/pdf")

    # 也尝试相对于当前工作目录的路径
    alt_path = f"project/{task_id}/paper.pdf"
    if os.path.exists(alt_path):
        return FileResponse(alt_path, media_type="application/pdf")

    raise HTTPException(status_code=404, detail="论文 PDF 不存在，请先运行建模任务")


@router.get("/preview/{task_id}/paper/content")
async def get_paper_content(task_id: str):
    """获取论文内容"""
    task = _get_task(task_id)

    content = task.get("paper_content")
    if not content:
        return {
            "task_id": task_id,
            "content": "# 暂无论文内容\n\n请等待建模任务完成生成论文。",
            "format": "markdown"
        }

    return {
        "task_id": task_id,
        "content": content,
        "format": "markdown"
    }


class UpdatePaperRequest(BaseModel):
    content: str


@router.put("/preview/{task_id}/paper/content")
async def update_paper_content(task_id: str, request: UpdatePaperRequest):
    """更新论文内容（写入数据库）"""
    from app.models.database import TaskDB, SessionLocal

    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        task.paper_content = request.content
        task.updated_at = datetime.now()
        db.commit()
        return {"message": "论文内容已更新"}
    finally:
        db.close()


@router.get("/preview/{task_id}/code")
async def get_code(task_id: str, language: str = "python"):
    """获取代码"""
    task = _get_task(task_id)

    code = task.get("code")
    if not code:
        return {
            "task_id": task_id,
            "language": language,
            "content": f"# {language} 代码\n# 暂无代码，请等待建模任务生成代码\n"
        }

    return {
        "task_id": task_id,
        "language": task.get("language", language),
        "content": code
    }


class UpdateCodeRequest(BaseModel):
    content: str
    language: str = "python"


@router.put("/preview/{task_id}/code")
async def update_code(task_id: str, request: UpdateCodeRequest):
    """更新代码（写入数据库）"""
    from app.models.database import TaskDB, SessionLocal

    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        task.code = request.content
        if request.language:
            task.language = request.language
        task.updated_at = datetime.now()
        db.commit()
        return {"message": "代码已更新"}
    finally:
        db.close()


@router.get("/preview/{task_id}/figures")
async def list_figures(task_id: str):
    """获取图表列表"""
    task = _get_task(task_id)

    raw_figures = task.get("figures", [])

    # 标准化格式：兼容字符串和 dict
    figures = []
    for fig in raw_figures:
        if isinstance(fig, str):
            figures.append({"name": fig, "url": f"/api/v1/preview/{task_id}/figures/{fig}", "type": "image"})
        elif isinstance(fig, dict):
            figures.append(fig)

    # 同时检查项目目录中的图表文件（补充数据库中没有的）
    base_dir = PROJECT_ROOT
    project_dir = os.path.join(base_dir, "project", task_id)

    if os.path.exists(project_dir):
        for f in os.listdir(project_dir):
            if f.endswith((".png", ".jpg", ".jpeg", ".svg", ".pdf")):
                existing_names = [fig.get("name", "") for fig in figures]
                if f not in existing_names:
                    figures.append({
                        "name": f,
                        "url": f"/api/v1/preview/{task_id}/figures/{f}",
                        "type": "image"
                    })

    return {"task_id": task_id, "figures": figures}


@router.get("/preview/{task_id}/figures/{filename}")
async def get_figure_file(task_id: str, filename: str):
    """获取图表文件"""
    base_dir = PROJECT_ROOT
    file_path = os.path.join(base_dir, "project", task_id, filename)

    if os.path.exists(file_path):
        media_type = "image/png"
        if filename.endswith(".jpg") or filename.endswith(".jpeg"):
            media_type = "image/jpeg"
        elif filename.endswith(".svg"):
            media_type = "image/svg+xml"
        elif filename.endswith(".pdf"):
            media_type = "application/pdf"
        return FileResponse(file_path, media_type=media_type)

    raise HTTPException(status_code=404, detail="图表文件不存在")


@router.post("/preview/{task_id}/code/run")
async def run_code(task_id: str, request: dict = {}):
    """执行代码"""
    import subprocess
    import tempfile

    language = request.get("language", "python")
    # 获取 task 的代码
    try:
        task = _get_task(task_id)
        code = task.get("code", "")
    except HTTPException:
        code = ""

    if not code.strip():
        return {"task_id": task_id, "output": "# 暂无代码可执行", "error": ""}

    try:
        if language == "python":
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(code)
                tmp_path = f.name
            result = subprocess.run(
                ["python", tmp_path], capture_output=True, text=True, timeout=30
            )
            os.unlink(tmp_path)
            return {
                "task_id": task_id,
                "output": result.stdout,
                "error": result.stderr,
            }
        else:
            return {"task_id": task_id, "output": f"暂不支持 {language} 语言在线执行", "error": ""}
    except subprocess.TimeoutExpired:
        return {"task_id": task_id, "output": "", "error": "代码执行超时 (30s)"}
    except Exception as e:
        return {"task_id": task_id, "output": "", "error": str(e)}


@router.post("/preview/{task_id}/figures/{filename}/export")
async def export_figure(task_id: str, filename: str, format: str = "png"):
    """导出图表文件"""
    base_dir = PROJECT_ROOT
    file_path = os.path.join(base_dir, "project", task_id, filename)

    if os.path.exists(file_path):
        media_type = "image/png" if format == "png" else "image/svg+xml"
        return FileResponse(file_path, media_type=media_type,
                           headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    raise HTTPException(status_code=404, detail="图表文件不存在")
