import React from "react";
import { renderToString } from "react-dom/server";
const App = () => React.createElement("div", { id: "a" }, "hello ", React.createElement("b", null, "world"));
console.log(renderToString(React.createElement(App)));
