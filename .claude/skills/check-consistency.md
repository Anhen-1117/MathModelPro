---
name: check-consistency
description: 后端修改后自动检查前后端一致性（字段名、API 路径、请求/响应格式），控制 token 消耗
---

# 前后端一致性检查

## 触发条件
当修改了后端以下内容时自动触发：
- API 端点路径、方法
- Pydantic 模型的字段名、类型、默认值
- 请求/响应格式
- 配置文件的 key 名

## 检查规则（按优先级）

### 1. 字段命名一致性（最常出问题）
- 后端 Pydantic 用 snake_case（`api_key`）→ 前端发的是 camelCase（`apiKey`）还是 snake_case？
- 快速 grep 命令：
  ```bash
  # 检查后端模型字段 vs 前端接口类型
  grep -rn "class.*Request\|class.*Response" backend/app/api/
  grep -rn "interface\|export type" frontend/src/apis/
  ```

### 2. API 路径一致性
- `curl` 快速验证（只验证状态码，不读响应体）：
  ```bash
  curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/v1/<endpoint>
  ```

### 3. 字段是否有遗漏
- 后端新增了字段？前端对应的 interface 加了吗？
- 后端改了默认值？前端默认值同步了吗？

### 4. Token 控制
- **只检查本次修改涉及的文件**，不扩大范围
- 用 `grep -n` 只看匹配行，不读整文件
- 优先用 `curl -o /dev/null -w "%{http_code}"` 验证，不读响应体
- 如果 3 个检查都通过，不输出长报告，只回复"前后端一致 ✅"
