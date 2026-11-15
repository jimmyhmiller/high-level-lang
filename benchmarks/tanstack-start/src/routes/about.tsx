import { createFileRoute } from "@tanstack/react-router";
import { createIsomorphicFn } from "@tanstack/react-start";
import { useState } from "react";

const where = createIsomorphicFn()
  .server(() => "on the server")
  .client(() => "in the browser");

export const Route = createFileRoute("/about")({
  loader: () => where(),
  component: About,
});

function About() {
  const loaded = Route.useLoaderData();
  const [clicked, setClicked] = useState("not yet");
  return (
    <div>
      <h1 data-testid="title">About</h1>
      <p data-testid="loaded">loaded {loaded}</p>
      <button data-testid="where" onClick={() => setClicked(where())}>clicked {clicked}</button>
    </div>
  );
}
