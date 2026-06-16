import request from "@/utils/request";
import type { Message } from "@/utils/response";

/** 健康检查 */
export function getHelloWorld() {
	return request.get<{ message: string }>("/api/v1/");
}

/** 获取论文写作顺序 */
export function getWriterSeque() {
	return request.get<{ writer_seque: string[] }>("/api/v1/writer_seque");
}

/**
 * 获取任务的历史消息
 * @param task_id 任务ID
 */
export function getTaskMessages(task_id: string) {
	return request.get<Message[]>("/api/v1/messages", {
		params: {
			task_id,
		},
	});
}

/**
 * 打开工作目录
 * @param task_id 任务ID
 */
export function openFolderAPI(task_id: string) {
	return request.get<{ message: string }>("/api/v1/open_folder", {
		params: {
			task_id,
		},
	});
}

/**
 * 提交样例任务
 * @param example_id 样例ID
 * @param source 来源
 */
export function exampleAPI(example_id: string, source: string) {
	return request.post<{
		task_id: string;
		status: string;
	}>("/api/v1/example", {
		example_id,
		source,
	});
}

/** 获取后端和 Redis 服务状态 */
export function getServiceStatus() {
	return request.get<{
		backend: { status: string; message: string };
		redis: { status: string; message: string };
	}>("/api/v1/status");
}

/**
 * 取消正在运行的任务
 * @param task_id 任务ID
 */
export function cancelTask(task_id: string) {
	return request.post<{ success: boolean; message: string }>(
		`/api/v1/tasks/${task_id}/cancel`,
	);
}
