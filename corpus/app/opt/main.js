import { add } from "fake-math/sum";
import text from "./hello.txt";
import b64 from "./hello.b64";
import url from "./hello.url";
console.log(add(2, 3), JSON.stringify(text), b64, url);
