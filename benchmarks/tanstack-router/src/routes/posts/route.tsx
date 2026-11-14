import { Link, Outlet, createFileRoute } from "@tanstack/react-router";
import { fetchPosts } from "../../api";

export const Route = createFileRoute("/posts")({
  loader: () => fetchPosts(),
  component: PostsLayout,
});

function PostsLayout() {
  const posts = Route.useLoaderData();
  return (
    <div>
      <h1 data-testid="title">Posts</h1>
      <ul>
        {posts.map((p) => (
          <li key={p.id}>
            <Link to="/posts/$postId" params={{ postId: p.id }}>{p.title}</Link>
          </li>
        ))}
      </ul>
      <Outlet />
    </div>
  );
}
