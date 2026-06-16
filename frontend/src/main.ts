import { createPinia } from "pinia";
import { createApp } from "vue";
import "./assets/style.css";
import "katex/dist/katex.min.css"; // KaTeX 数学公式全局样式
import App from "@/App.vue";
import router from "@/router";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);
const app = createApp(App);

app.use(router);
app.use(pinia);
app.mount("#app");
