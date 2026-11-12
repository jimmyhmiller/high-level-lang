// Elements without JSX, so no bundler needs a transform plugin to build the app.
import { createElement, Fragment } from "react";
import { renderToString } from "react-dom/server";

export const h = createElement;
export { Fragment };

// A page as HTML, and a short deterministic digest of it for the checks to compare.
export function rendered(tree) {
  const html = renderToString(tree);
  let hash = 0;
  for (let i = 0; i < html.length; i++) hash = (hash * 31 + html.charCodeAt(i)) | 0;
  return { length: html.length, hash };
}
