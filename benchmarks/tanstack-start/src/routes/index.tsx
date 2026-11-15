import { createFileRoute, useRouter } from "@tanstack/react-router";
import { createServerFn } from "@tanstack/react-start";
import { useState } from "react";
import { addCount, readCount } from "../server/store";

const getCount = createServerFn({ method: "GET" }).handler(async () => {
  return readCount();
});

const updateCount = createServerFn({ method: "POST" })
  .validator((d: number) => d)
  .handler(async ({ data }) => {
    return addCount(data);
  });

export const Route = createFileRoute("/")({
  loader: async () => await getCount(),
  component: Home,
});

function Home() {
  const router = useRouter();
  const count = Route.useLoaderData();
  const [clicks, setClicks] = useState(0);
  return (
    <div>
      <h1 data-testid="title">Start home</h1>
      <p data-testid="count">Server count: {count}</p>
      <button
        data-testid="add"
        onClick={async () => {
          await updateCount({ data: 1 });
          setClicks((c) => c + 1);
          router.invalidate();
        }}
      >
        Add one ({clicks})
      </button>
    </div>
  );
}
