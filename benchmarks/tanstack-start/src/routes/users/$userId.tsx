import { createFileRoute, notFound } from "@tanstack/react-router";
import { createServerFn } from "@tanstack/react-start";
import { findUser } from "../../server/store";

const getUser = createServerFn({ method: "GET" })
  .validator((id: string) => id)
  .handler(async ({ data }) => {
    const user = findUser(data);
    if (!user) throw notFound();
    return user;
  });

export const Route = createFileRoute("/users/$userId")({
  loader: ({ params }) => getUser({ data: params.userId }),
  component: User,
});

function User() {
  const user = Route.useLoaderData();
  return <h1 data-testid="title">User {user.name}</h1>;
}
