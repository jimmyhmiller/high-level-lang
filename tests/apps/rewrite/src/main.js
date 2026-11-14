import { get } from "tiny-get";
import { assert } from "./assert.js";
import { flags } from "./flags.js";
import { beta } from "./beta.js";

function local(get) {
  return get("x", 1);
}

const user = { profile: { name: "ada" } };
assert(user.profile, "user has a profile");
console.log(get(user, "profile").name, local((k, n) => k + n));
if (flags.beta) {
  console.log(beta());
}
