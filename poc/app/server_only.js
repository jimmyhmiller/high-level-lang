const connectionString = "postgres://secret-server-url";

export function readDatabase() {
  return "rows from " + connectionString;
}
