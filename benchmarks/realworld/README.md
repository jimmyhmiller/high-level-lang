# field-ops: a generated application on 59 packages

A React single-page app written for this benchmark, the way a team's app accretes dependencies:
each package is used the way its documentation shows, through the import style real code uses
(barrel imports from `@mui/material`, deep icon imports, `import * as d3`, `import * as R`, CommonJS
packages such as lodash, Papa Parse, qs and validator, plugins for Day.js, Markdown and Chart.js).
It type-checks with `npx tsc -p .`. About 500 installed packages.

Nine routes, each loaded with `import()`:

| Route | Packages |
|---|---|
| shell (`App.tsx`, `index.tsx`) | React 18, react-router-dom, Redux Toolkit, react-redux, TanStack Query, MUI + emotion, MUI icons, i18next, Sentry |
| Dashboard | recharts, Chart.js + react-chartjs-2, d3, decimal.js, date-fns, lodash-es |
| Customers | react-window, Fuse.js, libphonenumber-js, validator, clsx |
| Editor | react-markdown + remark-gfm, marked, DOMPurify, highlight.js, styled-components |
| Forms | react-hook-form + zod, Formik + yup, nanoid |
| Workflow | XState + @xstate/react, MobX + mobx-react-lite, jotai, zustand, immer, RxJS, socket.io-client |
| Graph | Apollo Client, graphql-js (a schema executed in the page) |
| 3D | three.js |
| Reports | Ramda, lodash, Papa Parse, Moment, Luxon, Day.js, qs |
| Motion | framer-motion, Floating UI, styled-components |

The data (`src/data.ts`) is seeded, and the HTTP layer (`src/api.ts`) is axios with an adapter
that answers from it, so the app needs no server and shows the same thing on every load.

## Checking a build

`tools/compare-bundlers.py --cases=field-ops` builds `src/index.tsx` with each bundler (code
splitting, ES modules, minified, `process.env.NODE_ENV` = `"production"`) and runs it in Chrome
(`benchmarks/bundlers/app-check.mjs`): it visits every route, searches the customer list, submits a
form with errors, moves the workflow through two states, and records the page's text at each step.
A build must throw nothing, fail no request, and show the same text at every step as the other
bundlers' builds do.
