import { createFileRoute } from "@tanstack/react-router";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { fetchPost } from "../../api";

export const Route = createFileRoute("/posts/$postId")({
  loader: ({ params }) => fetchPost(params.postId),
  errorComponent: PostError,
  component: PostComponent,
});

function PostError({ error }: ErrorComponentProps) {
  return <div data-testid="post-error">{(error as Error).message}</div>;
}

function PostComponent() {
  const post = Route.useLoaderData();
  return (
    <article>
      <h2 data-testid="post-title">{post.title}</h2>
      <p>{post.body}</p>
    </article>
  );
}
