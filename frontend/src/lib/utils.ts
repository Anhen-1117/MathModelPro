import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** 合并 Tailwind CSS 类名 */
export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

/** 更新表格的值 */
// biome-ignore lint/suspicious/noExplicitAny: 泛型约束需要 any
export function valueUpdater(updaterOrValue: any, ref: { value: any }) {
	ref.value =
		typeof updaterOrValue === "function"
			? updaterOrValue(ref.value)
			: updaterOrValue;
}
