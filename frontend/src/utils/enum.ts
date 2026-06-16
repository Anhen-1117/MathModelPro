/** Agent 类型枚举 — 值必须与后端 agent_type 字段一致（小写） */
export enum AgentType {
	COORDINATOR = "coordinator",
	MODELER = "modeler",
	CODER = "coder",
	WRITER = "writer",
}

/** LLM API 类型枚举 */
export enum ApiType {
	OPENAI_CHAT = "openai-chat",
	OPENAI_RESPONSES = "openai-responses",
	ANTHROPIC = "anthropic",
}
