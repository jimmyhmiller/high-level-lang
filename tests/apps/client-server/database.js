import "server-only";

// This sentinel must never appear in the browser output, even through an unused import.
const connection = "SERVER_DATABASE_SECRET_MUST_NOT_SHIP";
export function initialCount() {
  return connection.length > 0 ? 7 : 0;
}
