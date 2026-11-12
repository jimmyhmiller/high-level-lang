import { marked, Lexer } from "marked";
const md = "# Title\n\nSome *em* and **strong** text with `code` and a [link](http://x.y).\n\n- a\n- b\n  - c\n\n```js\nlet x = 1 < 2;\n```\n\n| h1 | h2 |\n|---|:-:|\n| 1 | 2 |\n\n> quote\n";
console.log(marked.parse(md)); console.log(Lexer.lex(md).map(t => t.type).join(","));
