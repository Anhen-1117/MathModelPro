<script setup lang="ts">
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
	SidebarMenuButton,
	SidebarMenuItem,
	SidebarMenuSub,
} from "@/components/ui/sidebar";
import { ChevronRight, File, Folder } from "lucide-vue-next";

// biome-ignore lint/suspicious/noExplicitAny: recursive tree structure
const props = defineProps<{
	item: any;
}>();

const name = String(Array.isArray(props.item) ? props.item[0] : props.item);
const items = Array.isArray(props.item) ? props.item.slice(1) : [];
</script>

<template>
  <SidebarMenuButton v-if="!items.length" :is-active="name === 'button.tsx'" class="data-[active=true]:bg-transparent">
    <File />
    {{ name }}
  </SidebarMenuButton>
  <SidebarMenuItem v-else>
    <Collapsible class="group/collapsible [&[data-state=open]>button>svg:first-child]:rotate-90"
      :default-open="name === 'components' || name === 'ui'">
      <CollapsibleTrigger as-child>
        <SidebarMenuButton>
          <ChevronRight class="transition-transform" />
          <Folder />
          {{ name }}
        </SidebarMenuButton>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <SidebarMenuSub>
          <Tree v-for="(subItem, index) in items" :key="index" :item="subItem" />
        </SidebarMenuSub>
      </CollapsibleContent>
    </Collapsible>
  </SidebarMenuItem>
</template>
