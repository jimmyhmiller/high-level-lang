# TanStack's own examples

Applications from TanStack's repository (`examples/react` at commit 0b6d4f3f6b42e704555d9ff0014ddbf8b44f8e09,
MIT, see LICENSE), each with the lockfile its install made: `npm ci --prefix benchmarks/tanstack-examples/NAME
--ignore-scripts`. `@tanstack/react-start` is pinned to 1.169.5, the newest published version (the repository asked
for an unreleased ^1.169.6); nothing else was changed.

`tools/tanstack-examples-check.py` builds each with us and with Vite and compares them in Chrome
(`tools/real-app-check.mjs`): every route without parameters, as the server sends it and as the page shows it
once hydrated, and the errors.
