import { Outlet, createFileRoute, redirect } from "@tanstack/react-router";

export const auth = { signedIn: true };

export const Route = createFileRoute("/_auth")({
  beforeLoad: ({ location }) => {
    if (!auth.signedIn) {
      throw redirect({ to: "/", search: { from: location.href } as never });
    }
  },
  component: () => (
    <section data-testid="auth-layout">
      <Outlet />
    </section>
  ),
});
