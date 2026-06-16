import { marked } from "marked";
import markedKatex from "marked-katex-extension";

// ── KaTeX 数学公式渲染 ─────────────────────────────────
marked.use(
	markedKatex({
		throwOnError: false,
		nonStandard: true,
	}),
);

// ── 默认渲染配置 ───────────────────────────────────────
const defaultOptions = {
	breaks: true,
	gfm: true,
};

// ── 图片 URL 重写 ──────────────────────────────────────
// 将相对路径的图片引用重写为完整的 API URL
const rewriteImageUrls = (markdown: string, taskId: string): string => {
	if (!taskId) return markdown;
	const baseUrl =
		import.meta.env.VITE_API_BASE_URL || window.location.origin;
	return markdown.replace(
		/!\[(.*?)\]\(((?!http[s]?:\/\/).*?\.(?:png|jpg|jpeg|gif|bmp|webp|svg|pdf))\)/g,
		(_: string, alt: string, src: string) =>
			`![${alt}](${baseUrl}/api/v1/preview/${taskId}/figures/${src})`,
	);
};

/**
 * 渲染 Markdown 文本为 HTML
 * @param content Markdown 文本
 * @param taskId  当前任务 ID（用于重写图片 URL）
 * @param options 可选的 marked 配置项
 */
export const renderMarkdown = async (
	content: string,
	taskId: string = "",
	options = {},
): Promise<string> => {
	const rewritten = taskId ? rewriteImageUrls(content, taskId) : content;
	const normalized = rewritten
		.replace(/\\\[\s*\n/g, "\\[")
		.replace(/\n\s*\\\]/g, "\\]");
	return marked.parse(normalized, { ...defaultOptions, ...options });
};

// 导出 marked 以备直接使用
export { marked };
