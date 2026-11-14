import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/posts/")({
  component: () => <p data-testid="posts-index">Pick a post.</p>,
});
