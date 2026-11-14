import { Link, Outlet, createRootRoute } from "@tanstack/react-router";

export const Route = createRootRoute({
  component: RootComponent,
  notFoundComponent: () => <p data-testid="not-found">Nothing here</p>,
});

function RootComponent() {
  return (
    <>
      <nav>
        <Link to="/" activeProps={{ className: "active" }} activeOptions={{ exact: true }}>Home</Link>
        <Link to="/about" activeProps={{ className: "active" }}>About</Link>
        <Link to="/posts" activeProps={{ className: "active" }}>Posts</Link>
        <Link to="/dashboard" activeProps={{ className: "active" }}>Dashboard</Link>
        <Link to="/pricing" search={{ plan: "pro" }} activeProps={{ className: "active" }}>Pricing</Link>
      </nav>
      <hr />
      <Outlet />
    </>
  );
}
