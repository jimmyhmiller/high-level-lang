export function query(q) {
  return "rows for " + q;
}

function connect() {
  return fetch("/db/connect");
}

export const pool = connect();
