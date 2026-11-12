import { reactive, computed, effect } from "vue";
const s = reactive({ a: 1 }); const c = computed(() => s.a * 2); const log = []; effect(() => log.push(c.value)); s.a = 5; console.log(log.join(","));
