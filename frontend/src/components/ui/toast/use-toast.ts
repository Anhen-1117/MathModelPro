import type { Component, VNode } from "vue";
import { computed, ref } from "vue";
import type { ToastProps } from ".";

const TOAST_LIMIT = 1;
const TOAST_REMOVE_DELAY = 1000000;

// biome-ignore lint/suspicious/noExplicitAny: avoiding deep type instantiation from reka-ui
export type StringOrVNode = string | VNode | (() => VNode);

type ToasterToast = {
	id: string;
	title?: string;
	description?: StringOrVNode;
	action?: Component;
	variant?: "default" | "destructive" | "success" | "warning" | "info";
	open?: boolean;
	onOpenChange?: (value: boolean) => void;
	[key: string]: any;
};

let count = 0;

function genId() {
	count = (count + 1) % Number.MAX_VALUE;
	return count.toString();
}

interface State {
	toasts: ToasterToast[];
}

const toastTimeouts = new Map<string, ReturnType<typeof setTimeout>>();

function addToRemoveQueue(toastId: string) {
	if (toastTimeouts.has(toastId)) return;

	const timeout = setTimeout(() => {
		toastTimeouts.delete(toastId);
		dispatch({
			type: "REMOVE_TOAST",
			toastId,
		});
	}, TOAST_REMOVE_DELAY);

	toastTimeouts.set(toastId, timeout);
}

const state = ref<State>({
	toasts: [],
});

// biome-ignore lint/suspicious/noExplicitAny: action dispatch needs any
function dispatch(action: any) {
	switch (action.type) {
		case "ADD_TOAST":
			state.value.toasts = [action.toast, ...state.value.toasts].slice(
				0,
				TOAST_LIMIT,
			);
			break;

		case "UPDATE_TOAST":
			state.value.toasts = state.value.toasts.map((t) =>
				t.id === action.toast.id ? { ...t, ...action.toast } : t,
			);
			break;

		case "DISMISS_TOAST": {
			const { toastId } = action;

			if (toastId) {
				addToRemoveQueue(toastId);
			} else {
				state.value.toasts.forEach((toast) => {
					addToRemoveQueue(toast.id);
				});
			}

			state.value.toasts = state.value.toasts.map((t) =>
				t.id === toastId || toastId === undefined
					? {
							...t,
							open: false,
						}
					: t,
			);
			break;
		}

		case "REMOVE_TOAST":
			if (action.toastId === undefined) state.value.toasts = [];
			else
				state.value.toasts = state.value.toasts.filter(
					(t) => t.id !== action.toastId,
				);

			break;
	}
}

// biome-ignore lint/suspicious/noExplicitAny: toast props need any
function toast(props: any) {
	const id = genId();

	const update = (props: ToasterToast) =>
		dispatch({
			type: "UPDATE_TOAST",
			toast: { ...props, id },
		});

	const dismiss = () =>
		dispatch({ type: "DISMISS_TOAST", toastId: id });

	dispatch({
		type: "ADD_TOAST",
		toast: {
			...props,
			id,
			open: true,
			onOpenChange: (open: boolean) => {
				if (!open) dismiss();
			},
		},
	});

	return {
		id,
		dismiss,
		update,
	};
}

function useToast() {
	return {
		toasts: computed(() => state.value.toasts),
		toast,
		dismiss: (toastId?: string) =>
			dispatch({ type: "DISMISS_TOAST", toastId }),
	};
}

export { toast, useToast };
