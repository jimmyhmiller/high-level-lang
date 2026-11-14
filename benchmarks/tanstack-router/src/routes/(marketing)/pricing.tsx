import { createFileRoute } from "@tanstack/react-router";

type Search = { plan: "free" | "pro" };

export const Route = createFileRoute("/(marketing)/pricing")({
  validateSearch: (search: Record<string, unknown>): Search => ({
    plan: search.plan === "pro" ? "pro" : "free",
  }),
  component: Pricing,
});

function Pricing() {
  const { plan } = Route.useSearch();
  return <h1 data-testid="title">Pricing: {plan}</h1>;
}
