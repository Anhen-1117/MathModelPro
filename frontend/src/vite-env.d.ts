/// <reference types="vite/client" />

declare module "*.vue" {
	import type { DefineComponent } from "vue";
	// biome-ignore lint/suspicious/noExplicitAny: Vue 组件类型声明需要 any
	// biome-ignore lint/complexity/noBannedTypes: Vue 组件类型声明需要 {}
	const component: DefineComponent<{}, {}, any>;
	export default component;
}

// 环境变量类型声明
interface ImportMetaEnv {
	/** WebSocket 服务地址（可选，默认从 window.location 推导） */
	readonly VITE_WS_URL?: string;
	/** API 基础 URL（可选，默认 "/"） */
	readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
