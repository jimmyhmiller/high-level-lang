import { pad } from "tiny-dup";

export function fmt(x) {
  return pad(String(x));
}

export function shout(x) {
  return x.toUpperCase();
}
