# CLAUDE.md — MathModelPro 项目规则

## 语言规则

请始终用中文回复。变量名保持英文。

## 核心设计规则

**所有改动必须从整体设计或模块设计层面来修改，禁止零散的、孤立的修补。**

### 具体含义

1. 修改某项功能时，先想清楚它属于哪个模块，模块的职责边界是什么
2. 不要头疼医头——如果 Word 格式有问题、PDF 格式也有问题，应该统一模板系统，而不是分别改 docx_exporter.py 和 PaperPreview.vue
3. 新功能的添加应该考虑它在整体架构中的位置，与现有模块的关系
4. 修改前先回答：这个改动在哪个模块？会影响哪些其他模块？有没有重复代码可以合并？

### 应用方式

- 遇到问题时：先分析模块架构 → 设计统一方案 → 再动手
- 看到重复代码/样式 → 提取为共享模块
- 双轨问题（V1/V2）：逐步收敛到统一架构
- 硬编码配置 → 提取到统一配置模块

## 项目结构

```
backend/
├── app/
│   ├── utils/          # 共享工具（paper_style, docx_exporter, llm_config）
│   ├── api/            # API 路由（tasks, preview, settings, chat, progress）
│   ├── core/engine/    # 核心引擎（workflow, evaluator, interpreter）
│   ├── domain/         # 新架构领域模型
│   ├── models/         # 数据库模型
│   └── services/       # 服务层（redis_manager）
├── data/               # 配置和模板
└── main.py             # 启动入口（@app.on_event）
frontend/
└── src/
    ├── pages/task/components/  # PaperPreview, TaskDetail
    ├── stores/                 # taskStore
    └── utils/                  # markdown.ts
```

## 关键约定

- 统一样式：`paper_style.py` 是 Word/PDF 的唯一样式源
- 前端 PDF 打印：通过 `GET /api/v1/template/styles` 获取 CSS
- 服务器启动：`main.py` 使用 `@app.on_event`，不再用 `@asynccontextmanager` + `yield`
- Launcher：`launcher.py` 的 `log()` 函数兼容 GBK 终端
