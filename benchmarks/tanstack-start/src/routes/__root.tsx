/// <reference types="vite/client" />
import type { ReactNode } from "react";
import { HeadContent, Link, Outlet, Scripts, createRootRoute } from "@tanstack/react-router";
import appCss from "../styles.css?url";

export const Route = createRootRoute({
  head: () => ({
    meta: [{ charSet: "utf-8" }, { name: "viewport", content: "width=device-width, initial-scale=1" }, { title: "TanStack Start app" }],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  component: RootComponent,
  notFoundComponent: () => <p data-testid="not-found">Nothing here</p>,
});

function RootComponent() {
  return (
    <RootDocument>
      <Outlet />
    </RootDocument>
  );
}

function RootDocument({ children }: { children: ReactNode }) {
  return (
    <html>
      <head>
        <HeadContent />
      </head>
      <body>
        <nav>
          <Link to="/" activeProps={{ className: "active" }} activeOptions={{ exact: true }}>Home</Link>{" "}
          <Link to="/about" activeProps={{ className: "active" }}>About</Link>{" "}
          <Link to="/users/$userId" params={{ userId: "2" }} activeProps={{ className: "active" }}>User 2</Link>
        </nav>
        {children}
        <Scripts />
      </body>
    </html>
  );
}
