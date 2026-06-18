<p align="center">
  <img src="frontend/public/favicon.svg" alt="MathModelPro" width="120" height="120">
</p>

<h1 align="center">MathModelPro</h1>

<p align="center">
  <strong>🧮 基于多智能体协作的数学建模竞赛全流程平台</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="Python">
  <img src="https://img.shields.io/badge/vue-3.5-brightgreen" alt="Vue">
  <img src="https://img.shields.io/badge/fastapi-0.115+-teal" alt="FastAPI">
</p>

---

## 📖 项目简介

MathModelPro 是一个面向数学建模竞赛的 AI 辅助平台，采用 **4 角色多智能体协作架构**（协调器、建模手、编程手、论文手），基于大语言模型（LLM）自动化完成从问题分析、模型构建、代码实现到论文生成的全流程。

### 核心特性

- 🤖 **多智能体协作** — Coordinator / Modeler / Coder / Writer 四角色流水线
- 📊 **可视化管线** — 自动生成折线图、柱状图、散点图、热力图等，并嵌入论文
- 📚 **文献管理** — 独立文献数据库，DOI 去重，BibTeX / GB/T 7714 参考文献导出
- 🔍 **RAG 知识库** — ChromaDB 向量检索 + TF-IDF 关键词双模式，辅助建模决策
- 📝 **论文自动生成** — Word + PDF 双格式输出，中文论文 3000+ 字
- ⏸️ **断点续传** — 四阶段检查点，支持暂停/恢复/重试
- 🌐 **实时通信** — WebSocket 实时日志推送 + SSE 流式对话
- 📎 **附件解析** — 上传 PDF/Word 自动提取文本，注入问题分析

## 🏗️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3.5 + Pinia + Vite + Tailwind CSS + ECharts + KaTeX |
| 后端 | FastAPI + SQLAlchemy + Redis + LiteLLM |
| 知识库 | ChromaDB + TF-IDF 双模式向量检索 |
| 代码执行 | Jupyter Kernel（沙箱隔离） |
| 文档导出 | python-docx（Word）+ Typst（PDF） |
| 可视化 | Matplotlib + Seaborn |
| LLM | 兼容 OpenAI API 的任意模型（默认 DeepSeek） |

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- pnpm（可选，自动回退到 npm）

### 1. 克隆项目

```bash
git clone --recurse-submodules https://github.com/Anhen-1117/MathModelPro.git
cd MathModelPro
```

### 2. 配置 API Key

```bash
# 复制配置模板
cp backend/data/config.example.json backend/data/config.json

# 编辑 config.json，填入你的 API Key
# 支持任意兼容 OpenAI API 的服务（DeepSeek / OpenAI / 本地模型等）
```

### 3. 一键启动

```bash
python launcher.py
```

启动器会自动：
- 检查环境和依赖
- 安装缺失的 Python/Node 包
- 启动后端（:8001）和前端（:5173）
- 打开浏览器

### 4. 手动启动

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# 前端（新终端）
cd frontend
pnpm install
pnpm dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:5173 |
| 后端 API | http://127.0.0.1:8001 |
| API 文档（Swagger） | http://127.0.0.1:8001/docs |
| 健康检查 | http://127.0.0.1:8001/health |

## 📂 项目结构

```
MathModelPro/
├── launcher.py                 # 统一启动器（环境检查 + 依赖安装 + 服务管理）
├── backend/
│   ├── app/
│   │   ├── api/                # API 路由层
│   │   │   ├── tasks.py        # 任务管理（V1，含断点续传）
│   │   │   ├── tasks_v2.py     # 任务管理（V2）
│   │   │   ├── preview.py      # 论文/图表预览
│   │   │   ├── chat.py         # SSE 流式对话
│   │   │   ├── knowledge.py    # 文献检索 + RAG
│   │   │   ├── skills.py       # 可视化 Skill 管线
│   │   │   ├── settings.py     # 配置管理（V1）
│   │   │   ├── settings_v2.py  # 配置管理（V2）
│   │   │   └── progress.py     # WebSocket 实时日志
│   │   ├── core/engine/        # 核心引擎
│   │   │   ├── workflow.py     # 主工作流（4 阶段流水线）
│   │   │   ├── evaluator.py    # 论文评估（一致性 + 公式自洽）
│   │   │   ├── interpreter.py  # Jupyter 代码执行沙箱
│   │   │   ├── rag.py          # RAG 知识检索（ChromaDB）
│   │   │   ├── literature.py   # 文献检索与管理
│   │   │   ├── knowledge.py    # 知识库引擎
│   │   │   └── i18n.py         # 中英文提示词模板
│   │   ├── domain/agent/       # 多智能体
│   │   │   ├── coordinator.py  # 协调器（问题分析 + 任务分配）
│   │   │   ├── modeler.py      # 建模手（模型选择 + 数学推导）
│   │   │   ├── coder.py        # 编程手（代码实现 + 可视化）
│   │   │   └── writer.py       # 论文手（Word/PDF 生成）
│   │   ├── domain/pipeline/    # 图表管线（V2 架构）
│   │   ├── models/database.py  # SQLite 数据模型
│   │   └── _paths.py           # 全局路径常量
│   ├── data/
│   │   ├── config.example.json # 配置模板（复制为 config.json）
│   │   ├── knowledge/          # 知识库文档
│   │   ├── skills/             # 可视化 Skill 定义
│   │   └── templates/          # Typst 论文模板
│   └── tests/                  # 后端测试
├── frontend/
│   ├── src/
│   │   ├── pages/task/         # 任务相关页面
│   │   ├── components/         # 通用组件
│   │   ├── stores/             # Pinia 状态管理
│   │   ├── apis/               # API 调用层
│   │   └── utils/              # 工具函数（Markdown 渲染等）
│   └── public/
│       └── favicon.svg         # 项目图标
└── .claude/skills/             # Claude Code 集成 Skill
```

## 🔄 工作流程

```
用户输入问题 → 协调器分析 → 建模手建模
                                    ↓
用户审阅论文 ← 论文手写作 ← 编程手求解 + 可视化
                                    ↓
                              评估器检查（一致性 + 公式自洽）
```

1. **协调器（Coordinator）** — 理解问题，提取关键信息，制定建模策略
2. **建模手（Modeler）** — 选择数学模型，RAG 辅助决策，输出推导过程
3. **编程手（Coder）** — 实现模型代码，Jupyter 沙箱执行，生成可视化图表
4. **论文手（Writer）** — 撰写完整论文（含公式、图表引用、参考文献）
5. **评估器（Evaluator）** — LLM 驱动的代码-论文一致性检查 + 公式自洽性验证

每个阶段都支持**断点保存**，可随时暂停/恢复。

## 🛠️ 启动器命令

```bash
python launcher.py [command] [options]

命令:
  start           启动全部服务（默认）
  stop            停止全部服务
  restart         重启全部服务
  status          查看服务状态
  check           环境与依赖检查
  backend         仅启动后端
  frontend        仅启动前端
  open            打开浏览器

选项:
  --auto, -a      自动模式（跳过交互确认）
  --no-browser    不自动打开浏览器
  --port-backend  指定后端端口（默认 8001）
  --port-frontend 指定前端端口（默认 5173）
```

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

<p align="center">
  <sub>Made with ❤️ for mathematical modeling enthusiasts</sub>
</p>
