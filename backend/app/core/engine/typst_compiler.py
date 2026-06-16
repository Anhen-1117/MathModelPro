"""Typst 论文编译器 — 17 套模板"""

import subprocess
import tempfile
import os
import shutil
from typing import Dict, Any, Optional, List
from pathlib import Path
from loguru import logger
from app._paths import data_dir


TEMPLATES_DIR = Path(data_dir("templates"))

# Typst 编译器路径：优先使用环境变量，其次检测 PATH 中的 typst，最后回退到硬编码路径
TYPST_PATH = os.environ.get("TYPST_PATH", "")
if not TYPST_PATH or not os.path.exists(TYPST_PATH):
    # 尝试在 PATH 中查找 typst
    typst_in_path = shutil.which("typst")
    if typst_in_path:
        TYPST_PATH = typst_in_path
    else:
        # 回退到可能的默认路径
        _candidates = [
            r"D:\_Dev\tools\typst\typst.exe",
            "/usr/local/bin/typst",
            "/usr/bin/typst",
        ]
        TYPST_PATH = next((c for c in _candidates if os.path.exists(c)), "typst")

# ── 模板注册 ──────────────────────────────────────────────

TEMPLATES = {
    # 中文模板
    "cumcm": {"name": "国赛 (CUMCM)", "lang": "zh", "dir": "mma/zh/cumcm", "main": "main.typ", "desc": "全国大学生数学建模竞赛"},
    "huashubei": {"name": "华数杯", "lang": "zh", "dir": "mma/zh/huashubei", "main": "main.typ", "desc": "华数杯数学建模竞赛"},
    "huaweibei": {"name": "华为杯", "lang": "zh", "dir": "mma/zh/huaweibei", "main": "main.typ", "desc": "华为杯研究生数学建模竞赛"},
    "mathorcup": {"name": "MathorCup", "lang": "zh", "dir": "mma/zh/mathorcup", "main": "main.typ", "desc": "MathorCup 高校数学建模挑战赛"},
    "diangongbei": {"name": "电工杯", "lang": "zh", "dir": "mma/zh/diangongbei", "main": "main.typ", "desc": "电工杯数学建模竞赛"},
    "wuyibei": {"name": "五一赛", "lang": "zh", "dir": "mma/zh/wuyibei", "main": "main.typ", "desc": "五一数学建模竞赛"},
    "huazhongbei": {"name": "华中杯", "lang": "zh", "dir": "mma/zh/huazhongbei", "main": "main.typ", "desc": "华中杯数学建模竞赛"},
    "shuweibei": {"name": "数维杯", "lang": "zh", "dir": "mma/zh/shuweibei", "main": "main.typ", "desc": "数维杯大学生数学建模竞赛"},
    "changsanjiao": {"name": "长三角", "lang": "zh", "dir": "mma/zh/changsanjiao", "main": "main.typ", "desc": "长三角数学建模竞赛"},
    "dongsansheng": {"name": "东三省", "lang": "zh", "dir": "mma/zh/dongsansheng", "main": "main.typ", "desc": "东三省数学建模联赛"},
    "zh_default": {"name": "中文通用", "lang": "zh", "dir": "mma/zh/default", "main": "main.typ", "desc": "中文通用论文模板"},
    "zh_stats": {"name": "统计分析", "lang": "zh", "dir": "mma/zh/stats", "main": "main.typ", "desc": "统计分析论文模板"},
    # 英文模板
    "mcm": {"name": "MCM/ICM (美赛)", "lang": "en", "dir": "mma/en/mcm", "main": "main.typ", "desc": "COMAP MCM/ICM 美国大学生数学建模竞赛"},
    "apmcm": {"name": "APMCM (亚太赛)", "lang": "en", "dir": "mma/en/apmcm", "main": "main.typ", "desc": "亚太地区大学生数学建模竞赛"},
    "en_default": {"name": "英文通用", "lang": "en", "dir": "mma/en/default", "main": "main.typ", "desc": "英文通用论文模板"},
    # 独立模板（从 GitHub 下载的）
    "cumcm_github": {"name": "国赛 (GitHub版)", "lang": "zh", "dir": "cumcm", "main": "template/main.typ", "desc": "GitHub 社区国赛模板"},
    "mcm_github": {"name": "MCM (GitHub版)", "lang": "en", "dir": "mcm", "main": "main.typ", "desc": "GitHub 社区美赛模板"},
}


class TypstCompiler:
    """Typst 编译器"""

    def __init__(self, typst_path: str = TYPST_PATH):
        self.typst_path = typst_path
        self.available = os.path.exists(typst_path)

    def get_templates(self) -> List[Dict[str, Any]]:
        """获取所有可用模板"""
        templates = []
        for tid, info in TEMPLATES.items():
            tdir = TEMPLATES_DIR / info["dir"]
            templates.append({
                "id": tid,
                "name": info["name"],
                "lang": info["lang"],
                "description": info["desc"],
                "available": tdir.exists(),
            })
        return templates

    def get_templates_by_lang(self, lang: str) -> List[Dict[str, Any]]:
        """按语言获取模板"""
        return [t for t in self.get_templates() if t["lang"] == lang]

    def compile(
        self,
        content: str,
        template_id: str = "cumcm",
        output_dir: Optional[str] = None,
        title: str = "数学建模论文",
    ) -> Dict[str, Any]:
        """编译论文为 PDF"""
        if not self.available:
            return {"success": False, "error": "Typst 未安装", "pdf_path": None}

        info = TEMPLATES.get(template_id)
        if not info:
            return {"success": False, "error": f"模板 {template_id} 不存在", "pdf_path": None}

        tdir = TEMPLATES_DIR / info["dir"]
        if not tdir.exists():
            return {"success": False, "error": f"模板目录不存在: {tdir}", "pdf_path": None}

        work_dir = tempfile.mkdtemp(prefix="mathmodel_")
        try:
            # 复制模板
            self._copy_template(tdir, work_dir)

            # 写入内容
            main_file = os.path.join(work_dir, info["main"])
            os.makedirs(os.path.dirname(main_file), exist_ok=True)

            if not content.strip().startswith("#"):
                content = self._markdown_to_typst(content, title)

            with open(main_file, "w", encoding="utf-8") as f:
                f.write(content)

            # 编译
            output_pdf = os.path.join(work_dir, "output.pdf")
            cmd = [self.typst_path, "compile", "--root", work_dir, main_file, output_pdf]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=work_dir)

            if result.returncode == 0 and os.path.exists(output_pdf):
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    final_path = os.path.join(output_dir, "paper.pdf")
                    shutil.copy2(output_pdf, final_path)
                else:
                    final_path = output_pdf

                return {"success": True, "pdf_path": final_path, "template": template_id, "size": os.path.getsize(final_path)}
            else:
                return {"success": False, "error": result.stderr[:500] if result.stderr else "编译失败", "pdf_path": None}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "编译超时", "pdf_path": None}
        except Exception as e:
            return {"success": False, "error": str(e), "pdf_path": None}
        finally:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except:
                pass

    def _copy_template(self, src: Path, dst: str):
        for item in src.iterdir():
            s, d = str(item), os.path.join(dst, item.name)
            if item.is_dir():
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

    def _markdown_to_typst(self, md: str, title: str) -> str:
        lines = md.split("\n")
        out = []
        for line in lines:
            if line.startswith("# "): out.append(f"= {line[2:]}")
            elif line.startswith("## "): out.append(f"== {line[3:]}")
            elif line.startswith("### "): out.append(f"=== {line[4:]}")
            else: out.append(line)
        return "\n".join(out)


typst_compiler = TypstCompiler()
