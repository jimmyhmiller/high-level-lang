import { Lexer } from "marked";
console.log(Lexer.lex("- a\n- b\n\n> q").map(t => t.type).join(","));
