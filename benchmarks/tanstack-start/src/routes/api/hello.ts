import { createFileRoute } from "@tanstack/react-router";

// A route only the server has: its handler must never reach the browser.
export const Route = createFileRoute("/api/hello")({
  server: {
    handlers: {
      GET: ({ request }) =>
        new Response(JSON.stringify({ hello: "SERVER_ROUTE_SECRET", path: new URL(request.url).pathname }), {
          headers: { "content-type": "application/json" },
        }),
    },
  },
});
