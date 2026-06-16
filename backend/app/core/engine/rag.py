"""RAG 知识库 — ChromaDB 向量检索 + Rerank 重排序

从本地知识库检索建模方法、代码模板、论文写作参考。
"""

import os
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from loguru import logger
from app._paths import data_dir


@dataclass
class KnowledgeDocument:
    """知识文档"""
    id: str
    title: str
    content: str
    category: str  # modeling / code / paper / general
    source: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RAGEngine:
    """RAG 检索引擎

    支持两种模式：
    1. ChromaDB 模式（需安装 chromadb）
    2. 内存模式（基于 TF-IDF 的轻量级检索，无需额外依赖）
    """

    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or os.path.join(
            data_dir("chromadb")
        )
        self._documents: Dict[str, KnowledgeDocument] = {}
        self._chroma_client = None
        self._collection = None
        self._use_chromadb = False
        self._initialized = False

    async def initialize(self):
        """初始化 RAG 引擎（重复调用安全，仅首次执行）"""
        if self._initialized:
            return
        self._initialized = True

        # 尝试使用 ChromaDB
        try:
            import chromadb
            from chromadb.config import Settings

            os.makedirs(self.persist_dir, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name="mathmodel_knowledge",
                metadata={"hnsw:space": "cosine"}
            )
            self._use_chromadb = True
            logger.info(f"ChromaDB 初始化成功: {self.persist_dir}")
        except ImportError:
            logger.warning("ChromaDB 未安装，使用内存 TF-IDF 模式")
        except Exception as e:
            logger.warning(f"ChromaDB 初始化失败: {e}，使用内存 TF-IDF 模式")

        # 加载内置知识库
        await self._load_builtin_knowledge()

    async def _load_builtin_knowledge(self):
        """加载内置建模知识库"""
        knowledge_dir = data_dir("knowledge")

        # 如果知识库目录不存在，创建默认知识
        if not os.path.exists(knowledge_dir):
            os.makedirs(knowledge_dir, exist_ok=True)
            await self._create_default_knowledge(knowledge_dir)

        # 加载知识文件
        for filename in os.listdir(knowledge_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(knowledge_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for doc in data:
                            await self.add_document(KnowledgeDocument(**doc))
                    elif isinstance(data, dict):
                        await self.add_document(KnowledgeDocument(**data))
                except Exception as e:
                    logger.warning(f"加载知识文件失败 {filename}: {e}")

        logger.info(f"知识库加载完成: {len(self._documents)} 篇文档")

    async def _create_default_knowledge(self, knowledge_dir: str):
        """创建默认建模知识库"""
        default_docs = [
            {
                "id": "model_linear_programming",
                "title": "线性规划 (Linear Programming)",
                "content": """线性规划是研究线性约束条件下线性目标函数极值问题的数学理论和方法。
适用场景：资源分配、生产计划、运输问题等。
典型解法：单纯形法 (Simplex Method)、内点法 (Interior Point Method)。
Python 实现：scipy.optimize.linprog, pulp。
关键步骤：1) 确定决策变量 2) 建立目标函数 3) 列出约束条件 4) 求解并分析。""",
                "category": "modeling",
                "tags": ["optimization", "linear", "资源分配", "生产计划"]
            },
            {
                "id": "model_nonlinear_programming",
                "title": "非线性规划 (Nonlinear Programming)",
                "content": """非线性规划处理目标函数或约束条件中至少有一个是非线性函数的优化问题。
适用场景：工程设计优化、投资组合优化、参数估计等。
解法：梯度下降法、牛顿法、SLSQP、遗传算法、粒子群算法。
Python 实现：scipy.optimize.minimize, scipy.optimize.differential_evolution。
注意事项：可能存在多个局部最优解，需要全局搜索方法。""",
                "category": "modeling",
                "tags": ["optimization", "nonlinear", "工程优化", "参数估计"]
            },
            {
                "id": "model_ahp",
                "title": "层次分析法 (AHP)",
                "content": """AHP 将决策问题分解为目标、准则、方案等层次，通过两两比较确定各因素权重。
适用场景：多准则决策、方案评估、供应商选择、风险评估等。
步骤：1) 建立层次结构模型 2) 构造判断矩阵 3) 层次单排序及一致性检验 4) 层次总排序。
注意：判断矩阵需要一致性检验，CR < 0.1 可接受。
Python：numpy 实现，或使用 pyDecision 库。""",
                "category": "modeling",
                "tags": ["评价", "决策", "多准则", "权重"]
            },
            {
                "id": "model_topsis",
                "title": "TOPSIS 优劣解距离法",
                "content": """TOPSIS 通过计算各方案与正理想解和负理想解的距离来排序方案优劣。
适用场景：多指标综合评价，如经济效益评价、环境质量评价、竞争力评价等。
步骤：1) 数据标准化 2) 确定正负理想解 3) 计算距离 4) 计算相对贴近度 5) 排序。
优点：对数据分布无要求，计算简单直观。
注意：指标需要同趋势化处理（正向化/负向化）。""",
                "category": "modeling",
                "tags": ["评价", "排序", "多指标", "综合评价"]
            },
            {
                "id": "model_arima",
                "title": "ARIMA 时间序列预测",
                "content": """ARIMA (AutoRegressive Integrated Moving Average) 是经典的时间序列预测方法。
适用场景：经济预测、销量预测、人口预测等趋势性数据。
模型参数：(p, d, q) — 自回归阶数、差分阶数、移动平均阶数。
步骤：1) 平稳性检验 (ADF) 2) 差分处理 3) 模型定阶 (AIC/BIC) 4) 残差检验。
Python：statsmodels.tsa.arima.model.ARIMA, pmdarima.auto_arima。
扩展：SARIMA (季节性), ARIMAX (外生变量)。""",
                "category": "modeling",
                "tags": ["预测", "时间序列", "经济", "统计"]
            },
            {
                "id": "model_ga",
                "title": "遗传算法 (Genetic Algorithm)",
                "content": """遗传算法模拟自然选择和遗传机制进行全局优化搜索。
适用场景：复杂非线性优化、路径规划、调度问题、参数优化等。
步骤：1) 编码 2) 初始化种群 3) 适应度评估 4) 选择 5) 交叉 6) 变异 7) 迭代。
参数：种群大小、交叉概率、变异概率、迭代次数。
Python：geneticalgorithm, DEAP, scipy.optimize.differential_evolution。
优点：全局搜索能力强，不要求目标函数可微。缺点：计算量大，收敛速度慢。""",
                "category": "modeling",
                "tags": ["优化", "进化算法", "全局搜索", "启发式"]
            },
            {
                "id": "code_template_py_optimization",
                "title": "Python 优化问题代码模板",
                "content": """Python 优化求解标准模板：
```python
import numpy as np
from scipy.optimize import minimize, linprog
import matplotlib.pyplot as plt

# 1. 定义目标函数
def objective(x):
    return x[0]**2 + x[1]**2

# 2. 定义约束条件
constraints = [
    {'type': 'ineq', 'fun': lambda x: x[0] + x[1] - 1},
    {'type': 'ineq', 'fun': lambda x: x[0]},
]

# 3. 求解
x0 = [0.5, 0.5]
result = minimize(objective, x0, constraints=constraints, method='SLSQP')
print(f"最优解: {result.x}")
print(f"最优值: {result.fun}")

# 4. 可视化
fig, ax = plt.subplots(figsize=(8, 6))
# ... 绘图代码 ...
plt.savefig('result.png', dpi=150)
```""",
                "category": "code",
                "tags": ["python", "optimization", "模板", "scipy"]
            },
            {
                "id": "code_template_py_prediction",
                "title": "Python 预测问题代码模板",
                "content": """Python 预测建模标准模板：
```python
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import matplotlib.pyplot as plt

# 1. 数据加载
df = pd.read_csv('data.csv')
X = df.drop('target', axis=1)
y = df['target']

# 2. 划分数据集
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# 3. 模型训练
from sklearn.ensemble import RandomForestRegressor
model = RandomForestRegressor(n_estimators=100)
model.fit(X_train, y_train)

# 4. 评估
y_pred = model.predict(X_test)
print(f"R²: {r2_score(y_test, y_pred):.4f}")
print(f"RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")

# 5. 可视化
plt.scatter(y_test, y_pred, alpha=0.5)
plt.plot([y.min(), y.max()], [y.min(), y.max()], 'r--')
plt.xlabel('真实值'); plt.ylabel('预测值')
plt.savefig('prediction_result.png', dpi=150)
```""",
                "category": "code",
                "tags": ["python", "prediction", "模板", "sklearn"]
            },
            {
                "id": "paper_structure",
                "title": "数学建模论文标准结构",
                "content": """标准数学建模论文结构：
1. **摘要** (Abstract)：问题背景、方法概述、主要结果、关键词。300-500字。
2. **问题重述** (Problem Restatement)：用自己的话重述问题，明确目标和约束。
3. **模型假设** (Assumptions)：列出建模过程中的关键假设和简化。
4. **符号说明** (Notation)：表格列出所有符号及其含义。
5. **模型建立** (Model)：核心部分，详细描述数学模型、公式推导。
6. **模型求解** (Solution)：算法描述、求解过程、结果呈现。
7. **结果分析** (Analysis)：对结果的解释、敏感性分析、模型检验。
8. **模型评价** (Evaluation)：优点、缺点、改进方向。
9. **参考文献** (References)：格式规范，引用近年文献。
10. **附录** (Appendix)：代码清单、详细数据等。""",
                "category": "paper",
                "tags": ["论文", "结构", "写作规范"]
            },
            {
                "id": "paper_common_mistakes",
                "title": "数学建模论文常见错误",
                "content": """数学建模论文常见错误：
1. **摘要过于简略**：需包含方法、主要数据和结论。
2. **没有明确假设**：缺少合理性和必要性的讨论。
3. **符号混乱**：同一符号在不同部分含义不同。
4. **模型没有求解过程**：只给出模型不给出解法。
5. **缺少敏感性分析**：没有分析参数变化对结果的影响。
6. **图表无标题和编号**：图表需有 Fig.1 或 表1 等编号和说明。
7. **引用不规范**：引用文献格式不统一，缺少页码或 DOI。
8. **代码未附在附录**：关键代码需要在附录中给出。
9. **结论与摘要不一致**：结论中的数据需与摘要呼应。
10. **没有讨论模型局限性**：所有模型都有局限，需要指出。""",
                "category": "paper",
                "tags": ["论文", "错误", "检查", "writing"]
            },
        ]

        filepath = os.path.join(knowledge_dir, "default_knowledge.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_docs, f, ensure_ascii=False, indent=2)

        logger.info(f"创建默认知识库: {len(default_docs)} 篇文档")

    async def add_document(self, doc: KnowledgeDocument):
        """添加文档到知识库"""
        self._documents[doc.id] = doc

        if self._use_chromadb and self._collection:
            try:
                self._collection.add(
                    ids=[doc.id],
                    documents=[doc.content],
                    metadatas=[{
                        "title": doc.title,
                        "category": doc.category,
                        "tags": ",".join(doc.tags),
                        "source": doc.source,
                    }],
                )
            except Exception as e:
                logger.warning(f"ChromaDB 添加文档失败: {e}")

    async def search(
        self,
        query: str,
        category: str = None,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> List[Tuple[KnowledgeDocument, float]]:
        """检索相关文档

        Args:
            query: 查询文本
            category: 过滤类别 (modeling/code/paper)
            top_k: 返回结果数
            use_rerank: 是否使用重排序

        Returns:
            (文档, 相关度分数) 列表
        """
        if self._use_chromadb and self._collection:
            results = await self._search_chromadb(query, category, top_k * 2)
        else:
            results = await self._search_tfidf(query, category, top_k * 3)

        if use_rerank and len(results) > top_k:
            results = await self._rerank(query, results, top_k)

        return results[:top_k]

    async def _search_chromadb(
        self, query: str, category: str = None, top_k: int = 10
    ) -> List[Tuple[KnowledgeDocument, float]]:
        """ChromaDB 检索"""
        try:
            where_filter = None
            if category:
                where_filter = {"category": category}

            response = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter,
            )

            results = []
            if response["ids"] and response["ids"][0]:
                for i, doc_id in enumerate(response["ids"][0]):
                    doc = self._documents.get(doc_id)
                    if doc:
                        distance = response["distances"][0][i] if response.get("distances") else 1.0
                        score = 1.0 - distance  # cosine distance → similarity
                        results.append((doc, score))
            return results
        except Exception as e:
            logger.warning(f"ChromaDB 检索失败: {e}，回退到 TF-IDF")
            return await self._search_tfidf(query, category, top_k)

    async def _search_tfidf(
        self, query: str, category: str = None, top_k: int = 10
    ) -> List[Tuple[KnowledgeDocument, float]]:
        """基于 TF-IDF 的内存检索（无需外部依赖）"""
        import re
        from collections import Counter
        from math import log

        # 分词（简单的中英文混合分词）
        def tokenize(text: str) -> List[str]:
            # 英文分词
            tokens = re.findall(r'[a-zA-Z]+', text.lower())
            # 中文按字符和双字符组合
            chinese = re.findall(r'[一-鿿]+', text)
            for chunk in chinese:
                tokens.extend(list(chunk))  # 单字
                tokens.extend([chunk[i:i+2] for i in range(len(chunk)-1)])  # 双字
            return tokens

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        N = len(self._documents)
        if N == 0:
            return []

        # 计算 IDF
        doc_token_sets = {}
        all_tokens = set()
        for doc_id, doc in self._documents.items():
            if category and doc.category != category:
                continue
            tokens = set(tokenize(doc.content + " " + doc.title))
            doc_token_sets[doc_id] = tokens
            all_tokens.update(tokens)

        df = Counter()
        for tokens in doc_token_sets.values():
            df.update(tokens)

        idf = {t: log((N + 1) / (df[t] + 1)) + 1 for t in all_tokens}

        # 计算 TF-IDF 相似度
        query_tf = Counter(query_tokens)
        query_vec = {t: (query_tf[t] / len(query_tokens)) * idf.get(t, 0)
                     for t in set(query_tokens)}

        results = []
        for doc_id, doc_tokens in doc_token_sets.items():
            doc = self._documents[doc_id]
            doc_vec = {t: 1.0 * idf.get(t, 0) for t in doc_tokens}

            # 余弦相似度
            dot = sum(query_vec.get(t, 0) * doc_vec.get(t, 0) for t in set(query_vec) | set(doc_vec))
            q_norm = sum(v**2 for v in query_vec.values()) ** 0.5
            d_norm = sum(v**2 for v in doc_vec.values()) ** 0.5

            if q_norm > 0 and d_norm > 0:
                score = dot / (q_norm * d_norm)
            else:
                score = 0.0

            if score > 0.01:  # 过滤极低相关度
                results.append((doc, score))

        return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]

    async def _rerank(
        self,
        query: str,
        candidates: List[Tuple[KnowledgeDocument, float]],
        top_k: int = 5,
    ) -> List[Tuple[KnowledgeDocument, float]]:
        """重排序

        使用多因子排序：
        1. 标题匹配度加成
        2. 标签匹配度加成
        3. 关键词密度加成
        """
        import re

        query_lower = query.lower()
        query_keywords = set(re.findall(r'[一-鿿]+|[a-zA-Z]+', query_lower))

        reranked = []
        for doc, base_score in candidates:
            score = base_score

            # 标题匹配加成 (最多 +0.3)
            title_match = sum(1 for kw in query_keywords if kw.lower() in doc.title.lower())
            if title_match > 0:
                score += 0.15 * title_match

            # 标签匹配加成 (最多 +0.2)
            tag_match = sum(1 for kw in query_keywords if any(kw in t.lower() for t in doc.tags))
            if tag_match > 0:
                score += 0.1 * tag_match

            # 精确关键词加成
            exact_match = sum(1 for kw in query_keywords if kw.lower() in doc.content.lower())
            score += 0.01 * min(exact_match, 10)

            reranked.append((doc, score))

        return sorted(reranked, key=lambda x: x[1], reverse=True)[:top_k]

    async def search_for_modeling(self, problem_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """为数学建模任务检索相关知识"""
        docs = await self.search(problem_text, category="modeling", top_k=top_k)
        return [
            {
                "title": doc.title,
                "content": doc.content,
                "score": round(score, 4),
                "tags": doc.tags,
            }
            for doc, score in docs
        ]

    async def search_for_coding(self, task_description: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """检索代码模板"""
        docs = await self.search(task_description, category="code", top_k=top_k)
        return [
            {
                "title": doc.title,
                "content": doc.content,
                "score": round(score, 4),
            }
            for doc, score in docs
        ]

    async def search_for_paper(self, topic: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """检索论文写作参考"""
        docs = await self.search(topic, category="paper", top_k=top_k)
        return [
            {
                "title": doc.title,
                "content": doc.content,
                "score": round(score, 4),
            }
            for doc, score in docs
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计"""
        categories = {}
        for doc in self._documents.values():
            categories[doc.category] = categories.get(doc.category, 0) + 1
        return {
            "total_documents": len(self._documents),
            "categories": categories,
            "backend": "chromadb" if self._use_chromadb else "tfidf",
        }


# 全局实例
rag_engine = RAGEngine()
