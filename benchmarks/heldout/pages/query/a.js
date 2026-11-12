import { QueryClient } from "@tanstack/query-core";
const qc = new QueryClient(); console.log(JSON.stringify(await qc.fetchQuery({ queryKey: ["a"], queryFn: async () => 42 }))); qc.clear();
