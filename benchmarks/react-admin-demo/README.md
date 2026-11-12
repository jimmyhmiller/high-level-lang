# react-admin's e-commerce demo, as a bundler benchmark

A real application nobody tuned this bundler on: `examples/demo` of
[marmelab/react-admin](https://github.com/marmelab/react-admin) at commit `f2cb5144`, the "Posters
Galore" admin. React 19, MUI 7, react-query, react-router 7, Apollo and GraphQL, echarts, recharts,
faker data from `data-generator-retail`, and an msw service worker that plays the API. About 430
installed packages.

Copied from upstream: `src/`, `index.html`, `package.json`, `tsconfig.json`, `tsconfig.node.json`,
`vite.config.ts`. Packages are installed from npm (`npm ci`) at the versions in
`package-lock.json`, not linked to the monorepo's sources as upstream's Vite config does.

## One change to the sources

`src/reviews/reviewFilters.tsx` and `src/reviews/rowSx.tsx` import MUI's colors from
`@mui/material/colors` instead of `@mui/material/colors/green` and the like. Those deep paths
exist only through the alias upstream's `vite.config.ts` adds (`@mui/x/y` → `@mui/x/esm/y`); MUI 7's
package exports do not have them, so no bundler resolves them without that alias. The colors are
the same objects either way.

## Building it

Every bundler builds `src/index.tsx` with code splitting into ES modules, minified, with:

- `process.env.NODE_ENV` = `"production"`, `process.env.REACT_APP_DATA_PROVIDER` = `""` (the
  REST data provider, as upstream's default), `import.meta.env.MODE` = `"production"`;
- `.svg` imports as files whose URL the code gets;
- TypeScript and JSX compiled the way each tool does it (see `benchmarks/bundlers/build.mjs`).

`tools/compare-bundlers.py --cases=react-admin` runs each build and then checks it in Chrome
(`benchmarks/bundlers/app-check.mjs`): sign in as demo/demo, the dashboard must show "Monthly
Revenue", with no error thrown and no request failed. The data is random each load, so builds are
compared on that and not on the exact text.
