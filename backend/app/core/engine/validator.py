"""论文验收系统 — 文本泄漏检测 + 数值一致性 + 格式检查"""

import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field


@dataclass
class ValidationIssue:
    """验收问题"""
    severity: str  # error / warning / info
    category: str  # leak / number / format / structure
    message: str
    location: str = ""
    suggestion: str = ""


@dataclass
class ValidationReport:
    """验收报告"""
    total_score: int = 0  # 0-100
    issues: List[ValidationIssue] = field(default_factory=list)
    summary: str = ""

    def add_issue(self, severity: str, category: str, message: str, location: str = "", suggestion: str = ""):
        self.issues.append(ValidationIssue(
            severity=severity, category=category, message=message, location=location, suggestion=suggestion
        ))

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


class PaperValidator:
    """论文验收器"""

    # 常见 AI 泄漏词
    LEAK_PATTERNS = [
        (r"作为一个AI", "AI 身份泄漏"),
        (r"作为一个人工智能", "AI 身份泄漏"),
        (r"我是(?:一个)?(?:AI|人工智能|语言模型|助手)", "AI 身份泄漏"),
        (r"我(?:无法|不能|没办法)(?:访问|获取|查询|浏览)", "能力边界泄漏"),
        (r"(?:抱歉|对不起)[，,]我(?:无法|不能)", "道歉式泄漏"),
        (r"请注意[，,]以上(?:内容|数据|结果)(?:是)?(?:由|由AI|由模型)", "生成声明泄漏"),
        (r"(?:GPT|ChatGPT|Claude|Gemini|DeepSeek|LLM)", "模型名泄漏"),
        (r"(?:OpenAI|Anthropic|Google|百度|阿里)", "公司名泄漏"),
        (r"(?:训练数据|预训练|大语言模型|大模型)", "技术术语泄漏"),
        (r"(?:虚拟|模拟|假设)(?:的)?(?:数据|实验|结果)", "虚拟声明泄漏"),
    ]

    # 结构检查
    REQUIRED_SECTIONS = ["摘要", "问题重述", "模型假设", "模型建立", "模型求解", "结果分析"]
    RECOMMENDED_SECTIONS = ["符号说明", "模型评价", "参考文献"]

    def validate(self, paper_content: str, problem_text: str = "") -> ValidationReport:
        """完整验收"""
        report = ValidationReport()

        if not paper_content or len(paper_content) < 100:
            report.add_issue("error", "structure", "论文内容过短或为空")
            report.total_score = 0
            report.summary = "论文内容不完整，无法进行验收。"
            return report

        # 1. 文本泄漏检测
        self._check_leaks(paper_content, report)

        # 2. 结构检查
        self._check_structure(paper_content, report)

        # 3. 数值一致性
        self._check_numbers(paper_content, report)

        # 4. 格式检查
        self._check_format(paper_content, report)

        # 5. 内容质量
        self._check_quality(paper_content, report)

        # 计算总分
        report.total_score = self._calculate_score(report)
        report.summary = self._generate_summary(report)

        return report

    def _check_leaks(self, content: str, report: ValidationReport):
        """文本泄漏检测"""
        for pattern, desc in self.LEAK_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for m in matches:
                # 获取上下文
                start = max(0, m.start() - 20)
                end = min(len(content), m.end() + 20)
                context = content[start:end].replace("\n", " ")
                report.add_issue(
                    "error", "leak",
                    f"检测到 {desc}：「{context}」",
                    suggestion="删除或改写该段落，避免暴露 AI 生成痕迹"
                )

    def _check_structure(self, content: str, report: ValidationReport):
        """结构检查"""
        found_sections = []
        for section in self.REQUIRED_SECTIONS:
            if section in content:
                found_sections.append(section)
            else:
                report.add_issue(
                    "error", "structure",
                    f"缺少必要章节：「{section}」",
                    suggestion=f"请补充「{section}」部分"
                )

        for section in self.RECOMMENDED_SECTIONS:
            if section not in content:
                report.add_issue(
                    "warning", "structure",
                    f"建议添加章节：「{section}」",
                    suggestion=f"补充「{section}」会让论文更完整"
                )

        # 检查是否有摘要
        if "摘要" in content:
            # 检查摘要长度
            abstract_match = re.search(r"摘要[：:\s]*(.{50,500}?)(?:\n#|\n\n)", content, re.DOTALL)
            if abstract_match:
                abstract = abstract_match.group(1)
                if len(abstract) < 50:
                    report.add_issue("warning", "structure", "摘要过短，建议 200-500 字")

    def _check_numbers(self, content: str, report: ValidationReport):
        """数值一致性检查"""
        # 提取所有数字
        numbers = re.findall(r"[-+]?\d*\.?\d+", content)

        # 检查是否有明显不一致（同一数值在不同位置出现不同）
        # 这是一个简化检查
        if len(numbers) < 3:
            report.add_issue("warning", "number", "论文中数值较少，建议补充计算结果")

        # 检查 LaTeX 公式是否闭合
        latex_open = content.count("$$")
        if latex_open % 2 != 0:
            report.add_issue("warning", "format", "LaTeX 公式 $$ 可能未正确闭合")

        inline_latex = re.findall(r"\$[^$]+\$", content)
        if not inline_latex and len(content) > 500:
            report.add_issue("info", "format", "建议使用 $...$ 标记行内公式")

    def _check_format(self, content: str, report: ValidationReport):
        """格式检查"""
        # 检查图表编号
        figures = re.findall(r"图\s*\d+", content)
        tables = re.findall(r"表\s*\d+", content)

        if len(content) > 1000 and not figures and not tables:
            report.add_issue("warning", "format", "论文中没有图表编号，建议添加图表")

        # 检查参考文献
        if "参考文献" in content:
            refs = re.findall(r"\[\d+\]", content)
            if len(refs) < 2:
                report.add_issue("warning", "format", "参考文献数量较少，建议至少 3-5 篇")
        else:
            report.add_issue("warning", "format", "缺少参考文献部分")

        # 检查段落长度
        paragraphs = content.split("\n\n")
        for i, p in enumerate(paragraphs):
            if len(p) > 1000 and not p.startswith("#"):
                report.add_issue(
                    "info", "format",
                    f"第 {i+1} 段过长（{len(p)} 字），建议分段",
                    suggestion="长段落会影响可读性"
                )

    def _check_quality(self, content: str, report: ValidationReport):
        """内容质量检查"""
        # 检查是否有「待补充」「TODO」「TBD」等
        placeholders = re.findall(r"(?:待补充|TODO|TBD|待完善|占位|示例)", content, re.IGNORECASE)
        if placeholders:
            report.add_issue(
                "warning", "quality",
                f"发现 {len(placeholders)} 处占位符/待补充标记",
                suggestion="请完成所有待补充内容"
            )

        # 检查关键词重复
        words = re.findall(r"[\u4e00-\u9fff]{2,4}", content)
        if words:
            from collections import Counter
            common = Counter(words).most_common(5)
            for word, count in common:
                if count > 20 and word not in ["模型", "问题", "数据", "分析", "结果"]:
                    report.add_issue(
                        "info", "quality",
                        f"词语「{word}」出现 {count} 次，可能过度重复"
                    )

    def _calculate_score(self, report: ValidationReport) -> int:
        """计算总分（0-100）"""
        score = 100
        for issue in report.issues:
            if issue.severity == "error":
                score -= 10
            elif issue.severity == "warning":
                score -= 3
            elif issue.severity == "info":
                score -= 1
        return max(0, min(100, score))

    def _generate_summary(self, report: ValidationReport) -> str:
        """生成验收总结"""
        if report.total_score >= 90:
            return f"✅ 论文质量优秀（{report.total_score}分）。发现 {report.error_count} 个错误、{report.warning_count} 个警告。"
        elif report.total_score >= 70:
            return f"⚠️ 论文质量良好（{report.total_score}分），有 {report.error_count} 个错误需要修复。"
        elif report.total_score >= 50:
            return f"⚠️ 论文质量一般（{report.total_score}分），有 {report.error_count} 个错误、{report.warning_count} 个警告，建议修改后重新验收。"
        else:
            return f"❌ 论文质量较差（{report.total_score}分），有 {report.error_count} 个严重错误，需要大幅修改。"


# 全局实例
paper_validator = PaperValidator()
