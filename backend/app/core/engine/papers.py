"""获奖论文数据 — 参考 mathmodel-skill 的 empirical.json"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class PaperPattern:
    """获奖论文模式"""
    competition: str
    year: int
    award: str  # 国一/国二/省一/O/F/M/H
    problem: str  # A/B/C
    title: str
    key_features: List[str]
    model_types: List[str]
    writing_style: Dict[str, Any]
    common_mistakes: List[str]


# ── 获奖论文模式数据 ──────────────────────────────────────

CUMCM_PATTERNS = [
    PaperPattern(
        competition="CUMCM", year=2024, award="国一", problem="A",
        title="2024国赛A题优秀论文模式",
        key_features=["连续优化", "偏微分方程", "物理建模", "数值仿真"],
        model_types=["PDE", "优化", "有限元", "蒙特卡洛"],
        writing_style={"摘要": "200-300字，问题+方法+结果", "公式密度": "高", "图表数量": "8-12"},
        common_mistakes=["符号未定义", "公式编号错误", "图表无标题", "缺少灵敏度分析"],
    ),
    PaperPattern(
        competition="CUMCM", year=2024, award="国一", problem="B",
        title="2024国赛B题优秀论文模式",
        key_features=["离散优化", "组合问题", "整数规划", "启发式算法"],
        model_types=["整数规划", "遗传算法", "模拟退火", "贪心算法"],
        writing_style={"摘要": "200-300字，问题+方法+结果", "公式密度": "中", "图表数量": "6-10"},
        common_mistakes=["约束条件遗漏", "算法伪代码不清晰", "结果验证不足"],
    ),
    PaperPattern(
        competition="CUMCM", year=2024, award="国一", problem="C",
        title="2024国赛C题优秀论文模式",
        key_features=["数据分析", "统计建模", "机器学习", "可视化"],
        model_types=["回归分析", "随机森林", "XGBoost", "聚类分析"],
        writing_style={"摘要": "200-300字，问题+方法+结果", "公式密度": "低", "图表数量": "10-15"},
        common_mistakes=["数据预处理不充分", "特征工程描述不清", "模型对比不全面"],
    ),
]

MCM_PATTERNS = [
    PaperPattern(
        competition="MCM", year=2024, award="O", problem="A",
        title="2024美赛Outstanding论文模式",
        key_features=["创新模型", "深度分析", "优美排版", "完整推导"],
        model_types=["微分方程", "优化", "仿真", "灵敏度分析"],
        writing_style={"摘要": "1页，Background+Method+Results+Conclusion", "公式密度": "高", "图表数量": "8-15", "页数": "25-35"},
        common_mistakes=["Introduction太长", "缺少Sensitivity Analysis", "References格式不统一"],
    ),
    PaperPattern(
        competition="MCM", year=2024, award="F", problem="A",
        title="2024美赛Finalist论文模式",
        key_features=["完整推导", "较好排版", "有创新点"],
        model_types=["优化", "统计", "仿真"],
        writing_style={"摘要": "1页", "公式密度": "中", "图表数量": "6-12", "页数": "20-30"},
        common_mistakes=["Strengths/Weaknesses太短", "缺少Future Work"],
    ),
]

# ── 易错模式 ──────────────────────────────────────────────

COMMON_MISTAKES = {
    "CUMCM": [
        "摘要缺少关键数值结果",
        "符号说明不完整（首次出现的符号必须定义）",
        "图表缺少编号和标题（图1: xxx, 表1: xxx）",
        "公式没有编号（重要公式必须编号）",
        "缺少灵敏度分析（至少分析2-3个参数）",
        "模型评价太空泛（要有具体数据支撑）",
        "参考文献格式不规范",
        "代码放在附录而非正文",
        "缺少问题重述（不能直接抄题目，要改写）",
        "结论没有回答题目提出的问题",
    ],
    "MCM": [
        "Introduction太长（控制在1-2页）",
        "缺少Restatement of the Problem",
        "Assumptions没有说明理由",
        "Model Overview缺少流程图",
        "Sensitivity Analysis不够深入",
        "Strengths and Weaknesses太短",
        "References格式不统一（推荐APA格式）",
        "Executive Summary超过1页",
        "缺少Future Work部分",
        "图表质量差（要用专业绘图工具）",
    ],
}

# ── 建模规范 ──────────────────────────────────────────────

MODELING_GUIDELINES = {
    "摘要写作": {
        "CUMCM": "200-300字，包含：问题概述、建模方法、求解结果、主要结论",
        "MCM": "1页，包含：Background、Methodology、Key Results、Conclusion",
    },
    "公式规范": {
        "重要公式": "必须编号，如 (1) (2) (3)",
        "符号定义": "首次出现必须定义，集中在符号说明表",
        "LaTeX格式": "行内用 $...$，独立公式用 $$...$$ 或 \\begin{equation}",
    },
    "图表规范": {
        "编号": "图1, 图2... 表1, 表2...",
        "标题": "图的标题在下方，表的标题在上方",
        "分辨率": "至少 150 DPI，推荐 300 DPI",
        "字体": "图中文字不小于正文字号",
    },
    "参考文献": {
        "CUMCM": "GB/T 7714 格式",
        "MCM": "APA 格式",
        "数量": "至少 5-10 篇",
    },
}


class PaperDatabase:
    """获奖论文数据库"""

    def __init__(self):
        self.patterns = CUMCM_PATTERNS + MCM_PATTERNS
        self.mistakes = COMMON_MISTAKES
        self.guidelines = MODELING_GUIDELINES

    def get_patterns(self, competition: str = None, award: str = None) -> List[Dict[str, Any]]:
        """获取获奖论文模式"""
        result = self.patterns
        if competition:
            result = [p for p in result if p.competition == competition]
        if award:
            result = [p for p in result if p.award == award]
        return [
            {
                "competition": p.competition,
                "year": p.year,
                "award": p.award,
                "problem": p.problem,
                "title": p.title,
                "key_features": p.key_features,
                "model_types": p.model_types,
                "writing_style": p.writing_style,
            }
            for p in result
        ]

    def get_mistakes(self, competition: str = "CUMCM") -> List[str]:
        """获取常见易错点"""
        return self.mistakes.get(competition, [])

    def get_guidelines(self) -> Dict[str, Any]:
        """获取写作规范"""
        return self.guidelines

    def get_writing_guide(self, competition: str = "CUMCM") -> Dict[str, Any]:
        """获取写作指南"""
        return {
            "competition": competition,
            "mistakes": self.get_mistakes(competition),
            "guidelines": self.guidelines,
            "patterns": self.get_patterns(competition),
        }


# 全局实例
paper_database = PaperDatabase()
