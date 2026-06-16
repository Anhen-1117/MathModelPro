"""代码沙箱 — 安全隔离执行"""

import os
import time
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger
from app.core.engine.interpreter import LocalInterpreter
from app._paths import project_dir


@dataclass
class SandboxResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    figures: list[str] = field(default_factory=list)
    duration_ms: int = 0


class CodeSandbox:
    """代码沙箱执行器。包装 LocalInterpreter，增加图表收集和结果标准化。"""

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self._interpreter = LocalInterpreter(timeout=timeout)

    async def run(self, code: str, language: str = "python") -> SandboxResult:
        if not code.strip():
            return SandboxResult(success=False, stderr="空代码")

        # 记录执行前 figures 目录的快照
        figures_dir = Path(project_dir("figures"))
        before = set()
        if figures_dir.exists():
            before = set(figures_dir.glob("*.png")) | set(figures_dir.glob("*.svg"))

        t0 = time.time()
        try:
            result = self._interpreter.execute(
                code=code,
                language=language,
                work_dir=None,  # 使用默认临时目录
                timeout=self.timeout,
            )
        except Exception as e:
            logger.error(f"Sandbox 执行异常: {e}")
            return SandboxResult(
                success=False,
                stderr=str(e),
                duration_ms=int((time.time() - t0) * 1000),
            )

        duration_ms = int((time.time() - t0) * 1000)

        # 收集新增的图表文件
        new_figures = []
        if figures_dir.exists():
            after = set(figures_dir.glob("*.png")) | set(figures_dir.glob("*.svg"))
            new_figures = [str(f.relative_to(figures_dir.parent)) for f in (after - before)]

        return SandboxResult(
            success=result.success,
            stdout=result.output or "",
            stderr=result.error or "",
            figures=new_figures,
            duration_ms=duration_ms,
        )
