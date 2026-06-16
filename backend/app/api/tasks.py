"""任务管理 API — 使用 SQLite 持久化"""

import os
import re
import uuid
import json
import io
import zipfile
import shutil
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.services.redis_manager import redis_manager
from app.models.database import TaskDB, SessionLocal, get_db
from app.core.engine.workflow import WorkflowEngine
from app.utils.docx_exporter import markdown_to_docx
from loguru import logger
from app._paths import PROJECT_ROOT, data_dir, project_dir

router = APIRouter()

# 跟踪正在运行的后台任务（用于暂停/取消）
_running_tasks: dict[str, asyncio.Task] = {}


class UpdateTaskRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None


def get_llm_config():
    """从配置读取 LLM 配置 + 图表管线等完整配置"""
    import json
    from app.utils.llm_config import load_llm_config

    # 基础 LLM 配置
    config = load_llm_config("coordinator").to_legacy_llm_config()

    # 合并 config.json 中的图表管线配置（使用统一路径）
    config_path = data_dir("config.json")
    try:
        full_config = json.loads(open(config_path, encoding="utf-8").read())
        config["chart_pipeline_enabled"] = full_config.get("chart_pipeline_enabled", True)
        config["chart_pipeline"] = full_config.get("chart_pipeline", [])
        config["model"] = full_config.get("model", {})
    except Exception:
        pass

    return config


def _task_to_dict(task: TaskDB) -> Dict[str, Any]:
    """将 ORM 对象转为字典"""
    return {
        "id": task.id,
        "name": task.name,
        "description": task.description,
        "problem_text": task.problem_text,
        "language": task.language,
        "template_id": task.template_id,
        "status": task.status,
        "progress": task.progress or {},
        "agent_status": task.agent_status or {},
        "token_usage": task.token_usage or {},
        "paper_content": task.paper_content,
        "code": task.code,
        "figures": task.figures or [],
        "literature": task.literature or [],
        "notes": task.notes or "",
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


async def run_workflow_background(task_id: str):
    """后台运行工作流（支持断点续传）"""
    db: Session = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            return

        # 创建工作流引擎
        llm_config = get_llm_config()
        engine = WorkflowEngine(llm_config)

        # 进度回调（直接更新数据库）
        def on_progress(phase: str, progress: int, message: str = ""):
            try:
                t = db.query(TaskDB).filter(TaskDB.id == task_id).first()
                if t:
                    # 【修复】复制 dict，避免 SQLAlchemy JSON 列原地修改不触发变更检测
                    prog = dict(t.progress) if t.progress else {
                        "analysis": 0, "modeling": 0, "coding": 0, "paper": 0, "overall": 0
                    }
                    if phase in prog:
                        prog[phase] = progress
                    phases = ["analysis", "modeling", "coding", "paper"]
                    total = sum(prog.get(p, 0) for p in phases)
                    prog["overall"] = total // len(phases)
                    t.progress = prog  # 赋新 dict，SQLAlchemy 能正确检测到变更
                    t.updated_at = datetime.now()
                    db.commit()
                    # 同时通过 Redis 推送进度更新给 WebSocket 客户端
                    asyncio.ensure_future(redis_manager.publish_progress(task_id, prog))
            except Exception as e:
                logger.warning(f"Progress update failed: {e}")

        # 日志回调
        def on_log(agent: str, message: str, level: str = "info"):
            try:
                t = db.query(TaskDB).filter(TaskDB.id == task_id).first()
                if t:
                    # 【修复】复制 dict，避免 SQLAlchemy JSON 列原地修改不触发变更检测
                    agents = dict(t.agent_status) if t.agent_status else {
                        "coordinator": "idle", "modeler": "idle", "coder": "idle", "writer": "idle"
                    }
                    agents[agent] = "working" if level != "error" else "error"
                    t.agent_status = agents  # 赋新 dict
                    db.commit()
                # 同时通过 Redis 推送日志给 WebSocket 客户端
                asyncio.ensure_future(redis_manager.publish_message(
                    task_id, {"content": message, "type": level, "agent": agent}
                ))
            except Exception as e:
                logger.warning(f"Log update failed: {e}")

        # 断点回调：每个阶段完成后保存检查点到数据库
        async def on_checkpoint(checkpoint_data: Dict[str, Any]):
            try:
                t = db.query(TaskDB).filter(TaskDB.id == task_id).first()
                if t:
                    t.checkpoint = checkpoint_data
                    t.updated_at = datetime.now()
                    db.commit()
                    logger.info(f"断点已保存: {checkpoint_data.get('completed_stages', [])}")
            except Exception as e:
                logger.warning(f"断点保存失败: {e}")

        engine.set_callbacks(
            progress_callback=on_progress,
            log_callback=on_log,
            checkpoint_callback=on_checkpoint,
        )

        # 读取断点（resume 时使用）
        checkpoint = dict(task.checkpoint) if task.checkpoint else None
        if checkpoint and not checkpoint.get("completed_stages"):
            checkpoint = None  # 空检查点视为新任务

        # 运行工作流
        result = await engine.run(
            problem_text=task.problem_text,
            language=task.language,
            task_id=task_id,
            notes=task.notes or "",
            checkpoint=checkpoint,
        )

        # 更新任务结果
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if task:
            # 检查是否被暂停
            if result.get("status") == "paused":
                task.status = "paused"
                task.checkpoint = result.get("_checkpoint", {})
                task.updated_at = datetime.now()
                db.commit()
                logger.info(f"Task {task_id} paused at checkpoint: {result.get('_checkpoint', {}).get('completed_stages', [])}")
                await redis_manager.publish_message(task_id, {"content": "任务已暂停，可从断点恢复", "type": "warning"})
                return

            base_dir = PROJECT_ROOT
            project_dir = os.path.join(base_dir, "project", task_id)
            os.makedirs(project_dir, exist_ok=True)

            # 将图片从临时目录复制到项目目录
            figure_names = []
            for fpath in result.get("figures", []):
                if os.path.isfile(fpath):
                    fname = os.path.basename(fpath)
                    dest = os.path.join(project_dir, fname)
                    shutil.copy2(fpath, dest)
                    figure_names.append(fname)
                    logger.info(f"图片已复制: {fname} -> project/{task_id}/")

            task.status = "completed"
            task.paper_content = result.get("paper", {}).get("content", "")
            task.code = result.get("code", {}).get("code", "")
            task.figures = figure_names
            task.literature = result.get("literature", [])
            task.checkpoint = {}  # 清除断点（任务已完成）
            task.updated_at = datetime.now()
            task.completed_at = datetime.now()

            agents = dict(task.agent_status) if task.agent_status else {}
            for agent in agents:
                agents[agent] = "completed"
            agents["system"] = "real_llm_mode"
            task.agent_status = agents  # 赋新 dict，触发 SQLAlchemy 变更检测

            db.commit()
            logger.info(f"Task {task_id} completed")

        # 发布完成消息
        await redis_manager.publish_message(task_id, {"content": "任务完成", "type": "success"})

    except asyncio.CancelledError:
        # 任务被取消（暂停），状态已在 result 处理中更新
        logger.info(f"Task {task_id} cancelled (paused)")
    except Exception as e:
        logger.error(f"Workflow failed for task {task_id}: {e}")
        try:
            task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
            if task:
                task.status = "failed"
                task.updated_at = datetime.now()
                db.commit()
        except Exception:
            pass
        await redis_manager.publish_message(task_id, {"content": f"任务失败: {str(e)}", "type": "error"})
    finally:
        # 清理任务跟踪
        _running_tasks.pop(task_id, None)
        db.close()


@router.post("/extract-text")
async def extract_text_from_files(
    files: List[UploadFile] = File(...),
):
    """从上传的文档中提取文本（预览，不创建任务）— 供前端拖拽上传后预览"""
    import tempfile
    from app.utils.doc_parser import parse_uploaded_file, merge_extracted_texts

    results = []
    temp_dir = None

    try:
        temp_dir = tempfile.mkdtemp(prefix="mmpro_extract_")
        for f in files:
            if not f.filename:
                continue
            ext = os.path.splitext(f.filename)[1].lower()
            temp_path = os.path.join(temp_dir, f.filename)

            content = await f.read()
            with open(temp_path, "wb") as wf:
                wf.write(content)

            parsed = parse_uploaded_file(temp_path)
            results.append({
                "filename": f.filename,
                "extension": ext,
                "char_count": len(parsed["extracted_text"]),
                "extracted_text": parsed["extracted_text"],
                "error": parsed.get("error"),
            })

        combined_text = merge_extracted_texts(results)
        return {
            "combined_text": combined_text,
            "results": results,
        }
    except Exception as e:
        logger.error(f"文本提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"文本提取失败: {str(e)}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/tasks")
async def create_task(
    name: str = Form(...),
    description: str = Form(default=""),
    problem_text: str = Form(default=""),
    language: str = Form(default="python"),
    template_id: str = Form(default="cumcm"),
    notes: str = Form(default=""),
    files: List[UploadFile] = File(default=[]),
):
    """创建任务并自动开始 — 支持 JSON 和 multipart/form-data（含文件上传）"""
    from app.utils.doc_parser import parse_uploaded_file, merge_extracted_texts, TEXT_EXTRACT_EXTENSIONS

    task_id = str(uuid.uuid4())[:8]

    # 保存上传文件并提取文本
    file_names: list[str] = []
    extracted_texts: list[dict] = []

    if files:
        work_dir = os.path.join(
            PROJECT_ROOT,
            "project", task_id
        )
        os.makedirs(work_dir, exist_ok=True)

        for f in files:
            if f.filename:
                content = await f.read()
                file_path = os.path.join(work_dir, f.filename)
                with open(file_path, "wb") as wf:
                    wf.write(content)
                file_names.append(f.filename)

                # 如果是文档文件，提取文本
                ext = os.path.splitext(f.filename)[1].lower()
                if ext in TEXT_EXTRACT_EXTENSIONS:
                    parsed = parse_uploaded_file(file_path)
                    extracted_texts.append(parsed)
                    logger.info(f"文档解析: {f.filename} → {len(parsed['extracted_text'])} 字符"
                                + (f", 错误: {parsed['error']}" if parsed.get('error') else ""))

        # 如果提取到文本且用户未手动填写 problem_text，则自动填充
        if extracted_texts and not problem_text.strip():
            problem_text = merge_extracted_texts(extracted_texts)
            logger.info(f"从 {len(extracted_texts)} 个文档自动提取题目文本，共 {len(problem_text)} 字符")
        elif extracted_texts and problem_text.strip():
            # 用户已手动输入，将提取文本作为补充
            extracted_text = merge_extracted_texts(extracted_texts)
            problem_text = problem_text + "\n\n---\n【从上传文档自动提取】\n" + extracted_text

    db = SessionLocal()
    try:
        task = TaskDB(
            id=task_id,
            name=name,
            description=description or f"文件: {', '.join(file_names)}" if file_names else "",
            problem_text=problem_text,
            language=language,
            template_id="cumcm" if template_id.lower() in ("cumcm", "国赛", "china", "chinese") else template_id,
            notes=notes,
            status="running",
            progress={"analysis": 0, "modeling": 0, "coding": 0, "paper": 0, "overall": 0},
            agent_status={"coordinator": "idle", "modeler": "idle", "coder": "idle", "writer": "idle"},
            token_usage={"coordinator": 0, "modeler": 0, "coder": 0, "writer": 0, "total": 0},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        result = _task_to_dict(task)
    finally:
        db.close()

    # 存储任务 ID 到 Redis
    await redis_manager.set(f"task_id:{task_id}", task_id)

    # 后台启动工作流
    _running_tasks[task_id] = asyncio.create_task(run_workflow_background(task_id))

    return result


@router.post("/modeling")
async def create_modeling_task(
    ques_all: str = Form(...),
    comp_template: str = Form(default="CHINA"),
    format_output: str = Form(default="Markdown"),
    notes: str = Form(default=""),
    files: List[UploadFile] = File(default=[]),
):
    """前端 UserStepper 提交建模任务（FormData 格式）"""
    task_id = str(uuid.uuid4())[:8]

    # 保存上传文件到项目目录
    file_names = []
    if files:
        work_dir = os.path.join(
            PROJECT_ROOT,
            "project", task_id
        )
        os.makedirs(work_dir, exist_ok=True)
        for f in files:
            if f.filename:
                content = await f.read()
                file_path = os.path.join(work_dir, f.filename)
                with open(file_path, "wb") as wf:
                    wf.write(content)
                file_names.append(f.filename)

    db = SessionLocal()
    try:
        task = TaskDB(
            id=task_id,
            name=f"建模任务-{task_id}",
            description=f"模板: {comp_template}, 格式: {format_output}",
            problem_text=ques_all,
            language="python",
            template_id="cumcm" if comp_template.upper() in ("CHINA", "国赛") else "mcm",
            notes=notes,
            status="running",
            progress={"analysis": 0, "modeling": 0, "coding": 0, "paper": 0, "overall": 0},
            agent_status={"coordinator": "idle", "modeler": "idle", "coder": "idle", "writer": "idle"},
            token_usage={"coordinator": 0, "modeler": 0, "coder": 0, "writer": 0, "total": 0},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        result = _task_to_dict(task)
    finally:
        db.close()

    await redis_manager.set(f"task_id:{task_id}", task_id)
    _running_tasks[task_id] = asyncio.create_task(run_workflow_background(task_id))

    return result


@router.get("/tasks")
async def list_tasks():
    """获取任务列表（从 SQLite）"""
    db = SessionLocal()
    try:
        tasks = db.query(TaskDB).order_by(TaskDB.created_at.desc()).all()
        return {"total": len(tasks), "tasks": [_task_to_dict(t) for t in tasks]}
    finally:
        db.close()


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情（从 SQLite）"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return _task_to_dict(task)
    finally:
        db.close()


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, request: UpdateTaskRequest):
    """更新任务"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if request.name is not None:
            task.name = request.name
        if request.status is not None:
            task.status = request.status
            if request.status == "completed":
                task.completed_at = datetime.now()
            elif request.status == "running":
                task.started_at = datetime.now()
        task.updated_at = datetime.now()
        db.commit()
        db.refresh(task)
        return _task_to_dict(task)
    finally:
        db.close()


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        db.delete(task)
        db.commit()
    finally:
        db.close()
    await redis_manager.delete(f"task_id:{task_id}")
    return {"message": "Task deleted"}


@router.post("/tasks/{task_id}/start")
async def start_task(task_id: str):
    """手动开始任务"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        task.status = "running"
        task.started_at = datetime.now()
        task.updated_at = datetime.now()
        db.commit()

        _running_tasks[task_id] = asyncio.create_task(run_workflow_background(task_id))

        return {"message": "Task started", "task": _task_to_dict(task)}
    finally:
        db.close()


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        task.status = "cancelled"
        task.updated_at = datetime.now()
        db.commit()
        return {"message": "Task cancelled", "task": _task_to_dict(task)}
    finally:
        db.close()


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    """暂停任务（取消后台工作流并保存断点）"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status != "running":
            raise HTTPException(status_code=400, detail="只能暂停运行中的任务")

        # 取消正在运行的后台任务
        running_task = _running_tasks.get(task_id)
        if running_task and not running_task.done():
            running_task.cancel()
            logger.info(f"已发送取消信号给任务 {task_id}")

        task.status = "paused"
        task.updated_at = datetime.now()
        db.commit()
        return {"message": "Task paused", "task": _task_to_dict(task)}
    finally:
        db.close()


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """恢复任务（从断点重新启动工作流）"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status != "paused":
            raise HTTPException(status_code=400, detail="只能恢复已暂停的任务")

        # 清除旧的后台任务引用
        old_task = _running_tasks.pop(task_id, None)
        if old_task and not old_task.done():
            logger.warning(f"清理未完成的旧任务引用: {task_id}")

        task.status = "running"
        task.updated_at = datetime.now()
        db.commit()

        # 启动新的后台任务（会从断点恢复）
        new_task = _running_tasks[task_id] = asyncio.create_task(run_workflow_background(task_id))
        _running_tasks[task_id] = new_task

        return {"message": "Task resumed", "task": _task_to_dict(task)}
    finally:
        db.close()


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    """重试任务"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        task.status = "running"
        task.progress = {"analysis": 0, "modeling": 0, "coding": 0, "paper": 0, "overall": 0}
        task.updated_at = datetime.now()
        db.commit()
        _running_tasks[task_id] = asyncio.create_task(run_workflow_background(task_id))
        return {"message": "Task retry started", "task": _task_to_dict(task)}
    finally:
        db.close()


@router.post("/tasks/{task_id}/export")
async def export_task(task_id: str, export_type: str = "paper"):
    """导出任务结果 — 返回包含全部工件的 zip 文件"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        base_dir = PROJECT_ROOT
        project_dir = os.path.join(base_dir, "project", task_id)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. 打包项目目录中的文件
            if os.path.exists(project_dir):
                for filename in os.listdir(project_dir):
                    filepath = os.path.join(project_dir, filename)
                    if os.path.isfile(filepath):
                        # 图表文件直接放根目录
                        zf.write(filepath, filename)

            # 2. 将论文内容保存为 paper.md
            if task.paper_content:
                zf.writestr("paper.md", task.paper_content)

            # 3. 将代码保存为 code.py 或 code.m
            if task.code:
                ext = ".m" if task.language == "matlab" else ".py"
                zf.writestr(f"code{ext}", task.code)

        buffer.seek(0)
        return Response(
            content=buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="task_{task_id}.zip"'},
        )
    finally:
        db.close()


@router.post("/tasks/{task_id}/export/docx")
async def export_task_docx(task_id: str):
    """导出任务论文为 Word (.docx) 格式"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if not task.paper_content:
            raise HTTPException(status_code=400, detail="论文尚未生成，无法导出")

        # 计算项目目录（图片所在位置）
        base_dir = PROJECT_ROOT
        project_dir = os.path.join(base_dir, "project", task_id)

        # 将 Markdown 论文转换为 .docx（含图片嵌入）
        docx_bytes = markdown_to_docx(
            markdown_text=task.paper_content,
            title=task.name or "数学建模论文",
            project_dir=project_dir,
        )

        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=task_{task_id}.docx"},
        )
    finally:
        db.close()


# ── 通用 API（前端 apis/ 调用）─────────────────────────────


@router.get("/messages")
async def get_task_messages(task_id: str):
    """获取任务历史消息"""
    db = SessionLocal()
    try:
        task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
        if not task:
            return {"messages": []}
        return {
            "messages": [
                {"role": "user", "content": task.problem_text or ""},
                {"role": "assistant", "content": task.paper_content or "任务处理中..."},
            ]
        }
    finally:
        db.close()


@router.get("/files")
async def get_task_files(task_id: str):
    """获取任务工作区文件列表"""
    base_dir = PROJECT_ROOT
    work_dir = os.path.join(base_dir, "project", task_id)
    files = []
    if os.path.exists(work_dir):
        for f in os.listdir(work_dir):
            file_path = os.path.join(work_dir, f)
            if os.path.isfile(file_path):
                ext = f.rsplit(".", 1)[-1] if "." in f else ""
                files.append({"filename": f, "file_type": ext})
    return {"files": files}


@router.get("/download_url")
async def get_download_url(task_id: str, filename: str):
    """获取单个文件下载链接"""
    return {"download_url": f"/api/v1/preview/{task_id}/figures/{filename}"}


@router.get("/download_all_url")
async def get_download_all_url(task_id: str):
    """获取全部文件压缩包下载链接"""
    return {"download_url": f"/api/v1/preview/{task_id}/paper"}


@router.post("/example")
async def create_example_task(example_id: str, source: str = ""):
    """从样例创建建模任务"""
    task_id = str(uuid.uuid4())[:8]
    examples = {
        "1": "某工厂生产A、B两种产品，每件利润分别为4万元和3万元。A需1台机器加工2小时，B需1台机器加工1小时。每天机器可用8小时。求最大利润的生产方案。",
        "2": "分析某城市过去10年的PM2.5数据，预测未来3年趋势。",
        "3": "设计最优物流配送路线，使总运输成本最小。",
    }
    problem_text = examples.get(example_id, examples["1"])

    db = SessionLocal()
    try:
        task = TaskDB(
            id=task_id,
            name=f"样例任务-{task_id}",
            description=f"样例来源: {source}",
            problem_text=problem_text,
            language="python",
            template_id="cumcm",
            status="running",
            progress={"analysis": 0, "modeling": 0, "coding": 0, "paper": 0, "overall": 0},
            agent_status={"coordinator": "idle", "modeler": "idle", "coder": "idle", "writer": "idle"},
            token_usage={"coordinator": 0, "modeler": 0, "coder": 0, "writer": 0, "total": 0},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        result = _task_to_dict(task)
    finally:
        db.close()

    await redis_manager.set(f"task_id:{task_id}", task_id)
    _running_tasks[task_id] = asyncio.create_task(run_workflow_background(task_id))
    return result


@router.get("/status")
async def get_service_status():
    """获取后端和 Redis 服务状态"""
    redis_status = "disconnected"
    try:
        await redis_manager.get("health_check")
        redis_status = "connected"
    except Exception:
        pass
    return {
        "backend": {"status": "ok", "message": "MathModelPro 运行中"},
        "redis": {"status": redis_status, "message": "正常" if redis_status == "connected" else "使用内存模式"},
    }


# ── 通用端点 ────────────────────────────────────────────────

@router.get("/")
async def root():
    """根路由 — 健康探活"""
    return {"message": "Hello World", "service": "MathModelPro", "version": "1.0.0"}


# ── 论文写作顺序 ────────────────────────────────────────────

# CUMCM 国赛论文标准章节顺序
CUMCM_WRITER_SEQUE = [
    "摘要",
    "问题重述",
    "模型假设",
    "符号说明",
    "模型建立与求解",
    "模型评价与推广",
    "参考文献",
    "附录",
]

# MCM 美赛论文标准章节顺序
MCM_WRITER_SEQUE = [
    "Abstract",
    "Introduction",
    "Assumptions and Justifications",
    "Notations",
    "Model Establishment and Solution",
    "Sensitivity Analysis",
    "Model Evaluation and Strengths/Weaknesses",
    "References",
    "Appendix",
]


@router.get("/writer_seque")
async def get_writer_seque(template: str = "cumcm"):
    """获取论文写作章节顺序"""
    if template.lower() in ("mcm", "mcm_icm"):
        return {"writer_seque": MCM_WRITER_SEQUE}
    return {"writer_seque": CUMCM_WRITER_SEQUE}


# ── 打开工作目录 ────────────────────────────────────────────

@router.get("/open_folder")
async def open_folder(task_id: str):
    """在文件资源管理器中打开任务工作目录"""
    import subprocess
    import platform

    base_dir = PROJECT_ROOT
    work_dir = os.path.join(base_dir, "project", task_id)

    if not os.path.exists(work_dir):
        os.makedirs(work_dir, exist_ok=True)

    try:
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(["explorer", work_dir])
        elif system == "Darwin":
            subprocess.Popen(["open", work_dir])
        else:
            subprocess.Popen(["xdg-open", work_dir])
        return {"message": "打开工作目录成功", "work_dir": work_dir}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开工作目录失败: {str(e)}")
