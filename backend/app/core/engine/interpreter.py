"""本地代码解释器 — Python（matplotlib/seaborn/plotly 可视化）"""

import asyncio
import subprocess
import tempfile
import os
import shutil
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str
    error: str = ""
    figures: List[str] = field(default_factory=list)


class LocalInterpreter:
    """本地 Python 代码解释器

    在临时目录中执行 Python 代码，自动发现生成的图表文件（png/jpg/svg/pdf）。
    """

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    @staticmethod
    def is_language_available(language: str = "python") -> bool:
        """检查 Python 是否可用"""
        return bool(shutil.which("python") or shutil.which("python3"))

    async def execute(
        self,
        code: str,
        language: str = "python",
        working_dir: Optional[str] = None,
    ) -> ExecutionResult:
        """执行 Python 代码

        Args:
            code: 代码内容
            language: 语言（固定为 python）
            working_dir: 工作目录

        Returns:
            执行结果（含自动发现的图表文件列表）
        """
        lang = language.lower()

        if lang not in ("python", "py"):
            return ExecutionResult(
                success=False, output="",
                error=f"不支持的语言: {language}。MathModelPro 仅使用 Python（matplotlib/seaborn）进行可视化。",
            )

        if not self.is_language_available():
            return ExecutionResult(
                success=False, output="",
                error="Python 未安装。请安装 Python 3.8+。",
            )

        return await self._execute_script(code, working_dir)

    async def _execute_script(
        self,
        code: str,
        working_dir: Optional[str] = None,
    ) -> ExecutionResult:
        """执行 Python 脚本（异步非阻塞）"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8",
        ) as f:
            f.write(code)
            tmp_path = f.name

        # 确定工作目录
        cwd = working_dir or os.path.dirname(tmp_path)

        # 记录执行前已有的文件
        before_files = set()
        if os.path.exists(cwd):
            for fn in os.listdir(cwd):
                before_files.add(os.path.join(cwd, fn))

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", tmp_path,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout,
            )

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            # 发现新生成的图表文件
            figures = []
            if os.path.exists(cwd):
                for fn in os.listdir(cwd):
                    fpath = os.path.join(cwd, fn)
                    if fpath not in before_files and os.path.isfile(fpath):
                        if fn.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".pdf")):
                            figures.append(fpath)

            return ExecutionResult(
                success=proc.returncode == 0,
                output=output[-8000:],
                error=error[-4000:],
                figures=figures,
            )
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False, output="",
                error=f"代码执行超时（{self.timeout}s）",
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False, output="",
                error="Python 未安装。请安装 Python 3.8+。",
            )
        except Exception as e:
            return ExecutionResult(
                success=False, output="",
                error=f"执行异常: {str(e)}",
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
