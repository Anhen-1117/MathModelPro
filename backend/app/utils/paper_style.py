"""
论文模板统一样式定义
====================
Word 导出和 PDF 打印共享同一套模板配置。修改此文件后，两端自动跟随。

使用方式:
    from app.utils.paper_style import get_style, to_css
    style = get_style("cumcm")    # 获取 CUMCM 样式常量
    css = to_css("cumcm")         # 生成 PDF 用的 CSS 字符串
"""

# ── 模板注册表 ────────────────────────────────────────────

TEMPLATES: dict[str, dict] = {
    "cumcm": {
        "name": "国赛 (CUMCM)",
        "lang": "zh",
        "desc": "全国大学生数学建模竞赛",
    },
    "mcm": {
        "name": "美赛 (MCM/ICM)",
        "lang": "en",
        "desc": "美国大学生数学建模竞赛",
    },
    "mathorcup": {
        "name": "MathorCup",
        "lang": "zh",
        "desc": "MathorCup 高校数学建模挑战赛",
    },
}

# ── 页面设置 ──────────────────────────────────────────────

PAGE = {
    "size": "A4",
    "margin_top": "2.5cm",
    "margin_bottom": "2.5cm",
    "margin_left": "2.5cm",
    "margin_right": "2.5cm",
}

# ── 字体 ──────────────────────────────────────────────────

FONTS = {
    "body": "Times New Roman",
    "body_cjk": "宋体",
    "code": ["Courier New", "Consolas", "Menlo", "monospace"],
    "math": "Cambria Math",
}

# ── 字号（pt）──────────────────────────────────────────────

SIZES = {
    "title": 17,      # 论文标题
    "h1": 17,          # 一级标题
    "h2": 14,          # 二级标题
    "h3": 12,          # 三级标题
    "body": 12,        # 正文
    "code": 10,        # 代码块
    "table": 10.5,     # 表格
    "math": 11,        # 公式
}

# ── 段落格式 ──────────────────────────────────────────────

PARAGRAPH = {
    "first_line_indent": "2em",   # 首行缩进
    "text_align": "justify",       # 两端对齐
    "line_height": 1.8,            # 行高（相对字号）
    "spacing_after": 0.35,         # 段后间距（em）
}

# ── 标题 ──────────────────────────────────────────────────

HEADING = {
    "h1_align": "center",          # 一级标题居中
    "h1_bold": True,
    "h2_bold": True,
    "h3_bold": True,
}

# ── 三线表 ────────────────────────────────────────────────

TABLE = {
    "style": "three_line",         # 三线表（CUMCM 规范）
    "padding": 0.45,               # 单元格内边距（em）
    "header_bold": True,
}

# ── 代码块 ────────────────────────────────────────────────

CODE = {
    "background": "#f2f2f2",
    "border": "0.8pt solid #b3b3b3",
    "padding": "0.7em",
}

# ── 数学公式 ──────────────────────────────────────────────

MATH = {
    "font_size_scale": 1.05,       # 相对正文的比例
}

# ── 公共 API ──────────────────────────────────────────────

def get_style(template_id: str = "cumcm") -> dict:
    """获取指定模板的完整样式配置（供 docx_exporter 使用）"""
    template = TEMPLATES.get(template_id, TEMPLATES["cumcm"])
    return {
        "template": template,
        "page": PAGE,
        "fonts": FONTS,
        "sizes": SIZES,
        "paragraph": PARAGRAPH,
        "heading": HEADING,
        "table": TABLE,
        "code": CODE,
        "math": MATH,
    }


def get_template_list() -> list[dict]:
    """获取可用模板列表"""
    return [
        {"id": tid, "name": info["name"], "lang": info["lang"], "desc": info["desc"]}
        for tid, info in TEMPLATES.items()
    ]


def to_css(template_id: str = "cumcm") -> str:
    """生成 PDF 打印用的 CSS 样式字符串"""
    return f"""
@page {{ size: {PAGE['size']}; margin: {PAGE['margin_top']} {PAGE['margin_right']} {PAGE['margin_bottom']} {PAGE['margin_left']}; }}
body {{
  font-family: '{FONTS["body"]}', '{FONTS["body_cjk"]}', serif;
  font-size: {SIZES["body"]}pt; line-height: {PARAGRAPH["line_height"]};
  color: #000; margin: 0; padding: 0;
}}
p {{ text-indent: {PARAGRAPH["first_line_indent"]}; margin: {PARAGRAPH["spacing_after"]}em 0; text-align: {PARAGRAPH["text_align"]}; }}
h1 {{ text-align: center; font-size: {SIZES["h1"]}pt; font-weight: bold; text-indent: 0; }}
h2 {{ font-size: {SIZES["h2"]}pt; font-weight: bold; text-indent: 0; page-break-before: always; }}
h3 {{ font-size: {SIZES["h3"]}pt; font-weight: bold; text-indent: 0; page-break-after: avoid; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.6em 0; font-size: {SIZES["table"]}pt; page-break-inside: avoid; }}
table thead {{ border-top: 1.5pt solid #000; border-bottom: 0.75pt solid #000; }}
table tbody {{ border-bottom: 1.5pt solid #000; }}
th, td {{ padding: {TABLE["padding"]}em; text-align: center; }}
th {{ font-weight: bold; }}
pre {{ background: {CODE["background"]}; border: {CODE["border"]}; padding: {CODE["padding"]}; font-size: {SIZES["code"]}pt; overflow-x: auto; white-space: pre-wrap; font-family: {'", "'.join(FONTS["code"])}; text-indent: 0; }}
code {{ font-family: {'", "'.join(FONTS["code"])}; font-size: {SIZES["code"]}pt; }}
img {{ max-width: 100%; page-break-inside: avoid; display: block; margin: 0 auto; }}
figure {{ text-indent: 0; text-align: center; margin: 0.6em 0; }}
figcaption {{ font-size: {SIZES["table"]}pt; font-weight: bold; }}
ul, ol {{ text-indent: 0; padding-left: 2em; }}
li {{ text-indent: 0; }}
.katex {{ font-size: {MATH["font_size_scale"]}em; }}
.katex-display {{ margin: 0.7em 0; text-align: center; }}
@media print {{
  body {{ padding: 0; }}
  h2 {{ page-break-before: always; }}
  h3, table, pre {{ page-break-inside: avoid; }}
}}
"""
