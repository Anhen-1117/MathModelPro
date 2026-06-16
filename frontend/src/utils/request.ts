import axios from "axios";

/** 创建 axios 实例 */
const service = axios.create({
	baseURL: import.meta.env.VITE_API_BASE_URL || "/",
	timeout: 30000,
});

/** 请求拦截器 */
service.interceptors.request.use(
	(config) => {
		return config;
	},
	(error) => {
		console.error("[Request Error]", error);
		return Promise.reject(error);
	},
);

/** 响应拦截器 */
service.interceptors.response.use(
	(response) => {
		return response;
	},
	async (error) => {
		const config = error.config;

		// 自动重试（最多 2 次，仅限 GET 请求或网络错误）
		const maxRetries = 2;
		config._retryCount = config._retryCount || 0;

		if (
			config._retryCount < maxRetries &&
			(!error.response || error.code === "ECONNABORTED" || error.code === "ERR_NETWORK")
		) {
			config._retryCount++;
			// 指数退避延迟
			const delay = Math.pow(2, config._retryCount) * 1000;
			await new Promise((resolve) => setTimeout(resolve, delay));
			console.warn(`[Request Retry] 第 ${config._retryCount} 次重试: ${config.url}`);
			return service(config);
		}

		// 统一错误提示（接入 toast 通知）
		const isNetworkError = error.code === "ECONNABORTED" || error.code === "ERR_NETWORK";
		const isServerError = error.response?.status && error.response.status >= 500;
		const message =
			error.response?.data?.detail ||
			error.response?.data?.message ||
			(isNetworkError ? "请求超时，请检查后端是否启动" : isServerError ? "服务器内部错误" : "请求失败");

		// 静默导入 toast，避免非 browser 环境报错
		try {
			const { toast } = await import("@/components/ui/toast/use-toast");
			toast({
				title: `❌ ${message}`,
				description: error.config?.url || "",
				variant: "destructive",
				duration: 4000,
			});
		} catch {
			console.error(`[Response Error] ${error.config?.url}:`, message);
		}

		console.error(`[Response Error] ${error.config?.url}:`, message);

		return Promise.reject(error);
	},
);

export default service;
