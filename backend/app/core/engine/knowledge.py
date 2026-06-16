"""建模知识库 — 模型选择决策树 + 常见方法库"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class ModelInfo:
    """模型信息"""
    id: str
    name: str
    name_en: str
    category: str
    description: str
    applicable_scenarios: List[str]
    pros: List[str]
    cons: List[str]
    complexity: str  # 低/中/高
    tools: List[str]  # Python/MATLAB 等
    example_code: str = ""
    references: List[str] = field(default_factory=list)


# ── 模型数据库 ────────────────────────────────────────────

MODELS: List[ModelInfo] = [
    ModelInfo(
        id="ahp",
        name="层次分析法",
        name_en="AHP (Analytic Hierarchy Process)",
        category="评价类",
        description="通过构建层次结构和判断矩阵，对多准则决策问题进行定量化分析。",
        applicable_scenarios=["方案优选", "权重确定", "绩效评估", "风险评价"],
        pros=["简单直观", "可处理定性指标", "有成熟理论基础"],
        cons=["主观性强", "指标不宜过多（≤9个）", "一致性检验可能不通过"],
        complexity="低",
        tools=["Python", "MATLAB", "Excel"],
        example_code="import numpy as np\n\n# 判断矩阵\nA = np.array([[1, 3, 5], [1/3, 1, 3], [1/5, 1/3, 1]])\n# 求特征值和特征向量\neigenvalues, eigenvectors = np.linalg.eig(A)\nweights = eigenvectors[:, 0].real / eigenvectors[:, 0].real.sum()\nprint(f'权重: {weights}')",
        references=["Saaty T L. The Analytic Hierarchy Process. McGraw-Hill, 1980."]
    ),
    ModelInfo(
        id="topsis",
        name="TOPSIS 逼近理想解",
        name_en="TOPSIS (Technique for Order Preference by Similarity to Ideal Solution)",
        category="评价类",
        description="通过计算各方案与理想解和负理想解的距离，进行多指标综合评价。",
        applicable_scenarios=["多指标排序", "方案优选", "供应商选择", "城市排名"],
        pros=["客观赋权", "计算简单", "结果直观"],
        cons=["对异常值敏感", "指标需要同向化", "权重确定有主观性"],
        complexity="低",
        tools=["Python", "MATLAB"],
    ),
    ModelInfo(
        id="gray_prediction",
        name="灰色预测 GM(1,1)",
        name_en="Gray Prediction GM(1,1)",
        category="预测类",
        description="基于少量数据建立微分方程模型，适用于数据量少、变化趋势明显的预测问题。",
        applicable_scenarios=["短期预测", "数据量少（4-8个）", "趋势预测", "产量预测"],
        pros=["数据需求少", "计算简单", "短期预测效果好"],
        cons=["只适合指数增长", "中长期预测不准", "对数据质量要求高"],
        complexity="低",
        tools=["Python", "MATLAB"],
    ),
    ModelInfo(
        id="arima",
        name="ARIMA 时间序列",
        name_en="ARIMA (AutoRegressive Integrated Moving Average)",
        category="预测类",
        description="经典时间序列预测模型，适用于平稳或差分后平稳的时间序列数据。",
        applicable_scenarios=["时间序列预测", "股票预测", "气象预测", "销量预测"],
        pros=["理论成熟", "适用范围广", "可处理季节性"],
        cons=["需要大量数据", "需要平稳性检验", "参数选择复杂"],
        complexity="中",
        tools=["Python (statsmodels)", "R"],
    ),
    ModelInfo(
        id="regression",
        name="回归分析",
        name_en="Regression Analysis",
        category="预测类",
        description="建立因变量与自变量之间的函数关系，用于预测和因素分析。",
        applicable_scenarios=["因素分析", "趋势预测", "因果关系", "数据拟合"],
        pros=["直观易懂", "可解释性强", "应用广泛"],
        cons=["假设条件多", "对异常值敏感", "非线性关系需变换"],
        complexity="低",
        tools=["Python (scikit-learn)", "MATLAB", "Excel"],
    ),
    ModelInfo(
        id="linear_programming",
        name="线性规划",
        name_en="Linear Programming",
        category="优化类",
        description="在一组线性约束条件下，求解线性目标函数的最优值。",
        applicable_scenarios=["资源分配", "生产计划", "运输问题", "配料优化"],
        pros=["有全局最优解", "求解速度快", "理论成熟"],
        cons=["仅限线性关系", "连续变量", "确定性问题"],
        complexity="低",
        tools=["Python (scipy, PuLP)", "MATLAB", "Lingo"],
    ),
    ModelInfo(
        id="integer_programming",
        name="整数规划",
        name_en="Integer Programming",
        category="优化类",
        description="决策变量要求为整数的数学规划问题，适用于离散决策场景。",
        applicable_scenarios=["选址问题", "排班问题", "背包问题", "指派问题"],
        pros=["更符合实际", "可处理离散决策"],
        cons=["求解复杂度高", "可能无解", "计算时间长"],
        complexity="高",
        tools=["Python (PuLP, OR-Tools)", "MATLAB", "Lingo"],
    ),
    ModelInfo(
        id="genetic_algorithm",
        name="遗传算法",
        name_en="Genetic Algorithm (GA)",
        category="优化类",
        description="模拟生物进化过程的全局优化算法，适用于复杂非线性优化问题。",
        applicable_scenarios=["组合优化", "函数优化", "参数调优", "NP难问题"],
        pros=["全局搜索", "不需梯度信息", "适用性广"],
        cons=["收敛慢", "参数敏感", "不保证最优"],
        complexity="中",
        tools=["Python (DEAP)", "MATLAB"],
    ),
    ModelInfo(
        id="monte_carlo",
        name="蒙特卡洛模拟",
        name_en="Monte Carlo Simulation",
        category="模拟类",
        description="通过大量随机抽样来近似求解问题，适用于复杂系统的概率分析。",
        applicable_scenarios=["风险分析", "概率估计", "积分计算", "系统仿真"],
        pros=["适用性极广", "可处理高维问题", "直观"],
        cons=["计算量大", "精度依赖样本量", "随机性"],
        complexity="中",
        tools=["Python (numpy)", "MATLAB"],
    ),
    ModelInfo(
        id="fuzzy_evaluation",
        name="模糊综合评价",
        name_en="Fuzzy Comprehensive Evaluation",
        category="评价类",
        description="利用模糊数学处理评价中的模糊性和不确定性问题。",
        applicable_scenarios=["环境评价", "质量评估", "风险评估", "满意度评价"],
        pros=["处理模糊性", "符合实际", "灵活"],
        cons=["隶属函数确定主观", "计算复杂", "结果解释难"],
        complexity="中",
        tools=["Python", "MATLAB"],
    ),
    ModelInfo(
        id="bp_neural_network",
        name="BP 神经网络",
        name_en="BP Neural Network",
        category="预测类",
        description="多层前馈神经网络，通过反向传播算法训练，适用于非线性映射问题。",
        applicable_scenarios=["非线性预测", "模式识别", "函数逼近", "分类"],
        pros=["非线性拟合能力强", "自适应学习", "通用性好"],
        cons=["需要大量数据", "容易过拟合", "黑箱模型"],
        complexity="高",
        tools=["Python (PyTorch, TensorFlow)", "MATLAB"],
    ),
    ModelInfo(
        id="entropy_weight",
        name="熵权法",
        name_en="Entropy Weight Method",
        category="评价类",
        description="基于信息熵客观确定指标权重的方法，避免主观赋权的偏差。",
        applicable_scenarios=["权重确定", "多指标评价", "与TOPSIS结合"],
        pros=["完全客观", "计算简单", "可与其他方法结合"],
        cons=["仅反映数据差异", "不考虑实际重要性", "对数据质量敏感"],
        complexity="低",
        tools=["Python", "Excel"],
    ),
]

# ── 决策树 ────────────────────────────────────────────────

DECISION_TREE = {
    "root": {
        "question": "你的问题属于哪一类？",
        "options": [
            {"label": "评价/排序", "value": "evaluation", "next": "eval_type"},
            {"label": "预测/趋势", "value": "prediction", "next": "pred_type"},
            {"label": "优化/决策", "value": "optimization", "next": "opt_type"},
            {"label": "分类/聚类", "value": "classification", "next": "class_type"},
            {"label": "不确定", "value": "unknown", "next": "help"},
        ]
    },
    "eval_type": {
        "question": "评价问题的具体类型？",
        "options": [
            {"label": "确定权重", "value": "weight", "models": ["ahp", "entropy_weight"]},
            {"label": "方案排序", "value": "ranking", "models": ["topsis", "ahp"]},
            {"label": "模糊评价", "value": "fuzzy", "models": ["fuzzy_evaluation"]},
            {"label": "综合评价", "value": "comprehensive", "models": ["topsis", "ahp", "entropy_weight"]},
        ]
    },
    "pred_type": {
        "question": "预测问题的数据特征？",
        "options": [
            {"label": "数据量少（<10个）", "value": "few", "models": ["gray_prediction"]},
            {"label": "时间序列", "value": "timeseries", "models": ["arima"]},
            {"label": "因果关系", "value": "causal", "models": ["regression"]},
            {"label": "非线性关系", "value": "nonlinear", "models": ["bp_neural_network", "regression"]},
        ]
    },
    "opt_type": {
        "question": "优化问题的特征？",
        "options": [
            {"label": "线性约束+线性目标", "value": "linear", "models": ["linear_programming"]},
            {"label": "需要整数解", "value": "integer", "models": ["integer_programming"]},
            {"label": "复杂非线性", "value": "nonlinear", "models": ["genetic_algorithm"]},
            {"label": "不确定/随机", "value": "stochastic", "models": ["monte_carlo"]},
        ]
    },
    "class_type": {
        "question": "分类/聚类问题？",
        "options": [
            {"label": "有标签数据", "value": "supervised", "models": ["bp_neural_network", "regression"]},
            {"label": "无标签数据", "value": "unsupervised", "models": ["monte_carlo"]},
        ]
    },
    "help": {
        "question": "请描述你的问题，我来帮你推荐：",
        "suggestions": [
            "如果需要对多个方案打分排名 → TOPSIS / AHP",
            "如果需要预测未来趋势 → ARIMA / 灰色预测 / 回归",
            "如果需要找最优方案 → 线性规划 / 遗传算法",
            "如果数据很少 → 灰色预测 GM(1,1)",
            "如果需要确定权重 → AHP / 熵权法",
        ]
    }
}


class KnowledgeBase:
    """建模知识库"""

    def __init__(self):
        self.models = {m.id: m for m in MODELS}
        self.decision_tree = DECISION_TREE

    def get_all_models(self) -> List[Dict[str, Any]]:
        """获取所有模型"""
        return [
            {
                "id": m.id,
                "name": m.name,
                "name_en": m.name_en,
                "category": m.category,
                "description": m.description,
                "complexity": m.complexity,
                "scenarios": m.applicable_scenarios,
            }
            for m in MODELS
        ]

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """获取模型详情"""
        m = self.models.get(model_id)
        if not m:
            return None
        return {
            "id": m.id,
            "name": m.name,
            "name_en": m.name_en,
            "category": m.category,
            "description": m.description,
            "applicable_scenarios": m.applicable_scenarios,
            "pros": m.pros,
            "cons": m.cons,
            "complexity": m.complexity,
            "tools": m.tools,
            "example_code": m.example_code,
            "references": m.references,
        }

    def get_models_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按类别获取模型"""
        return [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "complexity": m.complexity,
                "scenarios": m.applicable_scenarios,
            }
            for m in MODELS
            if m.category == category
        ]

    def get_decision_tree(self) -> Dict[str, Any]:
        """获取决策树"""
        return self.decision_tree

    def recommend(self, problem_type: str = "", keywords: List[str] = None) -> List[Dict[str, Any]]:
        """根据问题类型和关键词推荐模型"""
        keywords = keywords or []
        scores = []

        for m in MODELS:
            score = 0
            # 问题类型匹配
            if problem_type and problem_type in m.category:
                score += 3
            # 关键词匹配
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in m.name.lower() or kw_lower in m.name_en.lower():
                    score += 2
                for s in m.applicable_scenarios:
                    if kw_lower in s.lower():
                        score += 1
            if score > 0:
                scores.append((score, m))

        scores.sort(key=lambda x: -x[0])
        return [
            {
                "id": m.id,
                "name": m.name,
                "category": m.category,
                "description": m.description,
                "complexity": m.complexity,
                "match_score": score,
            }
            for score, m in scores[:5]
        ]


# 全局实例
knowledge_base = KnowledgeBase()
