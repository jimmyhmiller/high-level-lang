const café = "naïve ☃ 😀 é";
const t = `tmpl ☃ ${café} 😀`;
const r = /[é-ñ]+☃/g, ru = /😀/u;
const o = { ключ: "значение", "ключ2": 1 };
// comment ☃
console.log(café, t, r.test("é"), ru.source, o.ключ, String.raw`☃☃`);
