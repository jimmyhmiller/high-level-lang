import { ref, shallowRef, readonly, isReadonly, toRaw } from "vue";
const r = ref({ a: 1 }); const ro = readonly(r.value); console.log(isReadonly(ro), toRaw(ro).a, shallowRef(2).value);
