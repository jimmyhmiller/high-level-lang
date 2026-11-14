import { createFileRoute } from "@tanstack/react-router";
import { Counter } from "../components/Counter";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  return (
    <div>
      <h1 data-testid="title">Welcome home</h1>
      <Counter label="clicks" />
    </div>
  );
}
