import { createServerOnlyFn } from "@tanstack/react-start";

// State that lives on the server only: the client must never ship it.
let count = 0;
const users: Record<string, { id: string; name: string }> = {
  "1": { id: "1", name: "Ada (SERVER_ONLY_SECRET_ROW)" },
  "2": { id: "2", name: "Grace" },
};

export const readCount = createServerOnlyFn(() => count);
export const addCount = createServerOnlyFn((by: number) => {
  count += by;
  return count;
});
export const findUser = createServerOnlyFn((id: string) => users[id] ?? null);
