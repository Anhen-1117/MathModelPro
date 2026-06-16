import { createRouter, createWebHistory } from "vue-router";

/** 路由配置 */
const routes = [
	{
		path: "/",
		component: () => import("@/pages/index.vue"),
	},
	{
		path: "/login",
		component: () => import("@/pages/login/index.vue"),
	},
	{
		path: "/chat",
		component: () => import("@/pages/chat/index.vue"),
	},
	{
		path: "/tasks",
		component: () => import("@/pages/task/index.vue"),
	},
	{
		path: "/task/:task_id",
		component: () => import("@/pages/task/index.vue"),
		props: true,
	},
	{
		path: "/compare",
		component: () => import("@/pages/compare/index.vue"),
	},
	{
		path: "/settings",
		component: () => import("@/pages/settings/index.vue"),
	},
	{
		path: "/skills",
		component: () => import("@/pages/skills/index.vue"),
	},
	{
		path: "/knowledge",
		component: () => import("@/pages/knowledge/index.vue"),
	},
];

/** 创建路由实例 */
const router = createRouter({
	history: createWebHistory(),
	routes,
});

export default router;
