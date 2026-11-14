import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/about")({
  component: About,
});

const facts = ["routes are files", "loaders run before render", "components load lazily"];

function About() {
  return (
    <div>
      <h1 data-testid="title">About</h1>
      <ul>
        {facts.map((f) => (
          <li key={f}>{f}</li>
        ))}
      </ul>
    </div>
  );
}
