import { greet } from "./greet.js";
import { readDatabase } from "./server_only.js";
import { renderWidget } from "./client_only.js";
import { neverUsed } from "./util.js";

const answer = 6 * 7;

function main() {
  console.log(greet("world"), answer);
  console.debug("debug output, stripped from the client");
  if (SERVER) {
    console.log(readDatabase());
  } else {
    console.log(renderWidget());
  }
  if (!SERVER && CLIENT) {
    console.log("client only path");
  }
}

main();
