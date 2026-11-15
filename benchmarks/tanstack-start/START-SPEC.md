# TanStack Start (React) build specification, read from the installed sources

What `@tanstack/react-start/plugin/vite` (`tanstackStart()`) does to an application, written so a
non-Vite bundler can reproduce it. Production build first; dev notes are in section 12.

Every statement below comes from the installed `dist` sources (paths are given) and, where marked
**[verified]**, from `npx vite build` output of the reference app in this directory and from
requests made to the built `dist/server/server.js`.

Installed versions:

| package | version |
|---|---|
| @tanstack/react-start | 1.169.5 |
| @tanstack/start-plugin-core | 1.171.56 |
| @tanstack/start-client-core | 1.170.39 |
| @tanstack/start-server-core | 1.169.45 |
| @tanstack/react-start-client / -server | 1.168.45 / 1.167.52 |
| @tanstack/start-fn-stubs | 1.162.0 |
| @tanstack/start-storage-context | 1.167.41 |
| @tanstack/router-plugin / router-generator / router-core / react-router | 1.169.0 / 1.168.0 / 1.171.39 / 1.170.46 |
| vite | 8.3.8 (Rolldown) |

Abbreviations: `NM = node_modules/@tanstack`, `SPC = NM/start-plugin-core/dist/esm`.

Note on the API: in this version the server function builder's input validation method is
**`.validator(...)`**, not `.inputValidator(...)` (`NM/start-client-core/dist/esm/createServerFn.js`
has `middleware`, `validator`, `handler` only; the compiler's method-chain table is
`{middleware, validator, handler, server, client}`). An app that calls `.inputValidator` would
fail with "inputValidator is not a function" on the client: the compiler leaves the call in place
and the runtime has no such method.

---

## 0. The whole pipeline

1. Resolve the Start config (`SPC/schema.js`, section 11) and the entry files (section 2).
2. The router generator writes `src/routeTree.gen.ts` (with a Start footer, section 10) and
   publishes `globalThis.TSS_ROUTES_MANIFEST` (routeId → `{filePath, children}`).
3. **Client build** (Vite environment `client`): input `{ index: "virtual:tanstack-start-client-entry" }`
   → `dist/client/assets/*`. The start compiler (section 4) runs as `env: "client"`. The router
   code splitter runs with `deleteNodes: ["ssr","server","headers"]`. The generated route tree is
   **replaced in memory** by a client tree (server-only routes pruned, no types; section 10).
   At `generateBundle`, the chunk graph is captured to build the start manifest later. Server
   functions found by the compiler are recorded in a registry shared across builds (`serverFnsById`).
4. **Server build** (Vite environment `ssr`): input = server entry → `dist/server/server.js` +
   `dist/server/assets/*`. Compiler as `env: "server"`. The virtual module
   `tanstack-start-manifest:v` is generated from the captured client bundle + routes manifest
   (section 7). The virtual module `#tanstack-start-server-fn-resolver` is generated from the
   `serverFnsById` registry (section 5); it dynamically imports one "provider" module
   (`<file>?tss-serverfn-split`) per file that defines server functions.
5. Post-build: prerender / SPA shell / sitemap. All are off by default (section 11).

Order: `buildApp` builds `client` then `ssr` (`SPC/vite/planning.js: buildStartViteEnvironments`).
The server build needs from the client build (a) the client chunk graph for the start manifest
and (b) the server functions the client referenced (to seed the registry and keep their ids
stable). The Rsbuild adapter shows the dependency is only on data, not on the build order: it builds
both in parallel, emits the manifest module as
`const tsrStartManifestData = "__TSS_START_MANIFEST_PLACEHOLDER__"` and patches the literal in
`processAssets` once the client build is done, and rebuilds the resolver module at `finishMake`,
after every module has been compiled (`SPC/rsbuild/virtual-modules.js`, `SPC/rsbuild/plugin.js`,
`SPC/rsbuild/server-fn-resolver-rebuild.js`).

---

## 1. Environments and builds

Source: `SPC/vite/plugin.js`, `SPC/vite/planning.js`, `SPC/vite/output-directory.js`,
`NM/react-start/dist/esm/plugin/vite.js`.

### 1.1 Environment names and types

`START_ENVIRONMENT_NAMES = { server: "ssr", client: "client" }` (`SPC/constants.js`).
React Start (no RSC): `providerEnvironmentName = "ssr"`, `ssrIsProvider = true`, so the SSR
build is also the provider of server function implementations. No third environment.

### 1.2 Vite config the plugin returns (config hook, `enforce: "pre"`)

```js
{
  appType: userConfig.appType ?? "custom",          // no index.html; no SPA fallback
  environments: {
    client: {
      consumer: "client",
      build: {
        rolldownOptions: { input: { index: command === "serve"
            ? "virtual:tanstack-start-dev-client-entry"
            : "virtual:tanstack-start-client-entry" } },
        outDir: <client out dir>,                    // default "dist/client"
      },
      optimizeDeps: { exclude: <crawled>, entries: [clientEntry, routerEntry] },
    },
    ssr: {
      consumer: "server",
      build: {
        ssr: true,
        rolldownOptions: { input: userSsrInput ?? <server entry path> },
        outDir: <server out dir>,                    // default "dist/server"
        commonjsOptions: { include: [/node_modules/] },
        copyPublicDir: userValue ?? false,           // public/ is copied only into dist/client
      },
      optimizeDeps: { entries: [serverEntry, startEntry, routerEntry] },
    },
  },
  resolve: {
    noExternal: ["@tanstack/start**", "@tanstack/react-start**", ...crawledFrameworkPkgs],
    alias: {
      "virtual:tanstack-start-client-entry": <client entry path>,
      "virtual:tanstack-start-server-entry": <server entry path>,
      "#tanstack-start-entry": <start entry path>,
      "#tanstack-router-entry": <router entry path>,
    },
  },
  define: { ...see section 11.1 },
  builder: { sharedPlugins: true, buildApp: build client, then ssr },
}
```

Output directories: `environments.<name>.build.outDir`, else `join(build.outDir ?? "dist", "client" | "server")`.

`crawledFrameworkPkgs` (vitefu `crawlFrameworkPkgs`): the app's dependencies whose
`peerDependencies` include `@tanstack/react-start` or `@tanstack/start-client-core`. None in the
reference app.

React-specific per-environment config (`react-start/dist/esm/plugin/vite.js`, `configEnvironment`):
`resolve.dedupe = ["react","react-dom","@tanstack/react-start","@tanstack/react-router"]`;
`resolve.external` of `@tanstack/react-router` only inside the TanStack monorepo (not here);
optimizeDeps include/exclude lists (dev only).

### 1.3 Resolve conditions

Start sets none. Vite defaults apply:
client `["module","browser","production"|"development"]`, SSR `["module","node","production"|"development"]`
(RSC adds `react-server`, not used). These conditions matter:

* `@tanstack/router-core/isServer` exports: `development` → `isServer = undefined`;
  `browser` → `false`; `node`/`worker`/`workerd`/`deno`/`bun` → `true` (`NODE_ENV==="test"` → undefined);
  default `import` → client (false).
* `@tanstack/react-router` `.`: `development` → `index.dev.js`.

Because router-core is **external** in the SSR build, Node resolves it at run time with the
`node` condition (server variant).

### 1.4 Externals

* Client: everything bundled.
* SSR: Vite's default SSR externalization (bare imports of packages in node_modules become
  external imports) **except** `resolve.noExternal`: `@tanstack/start**`, `@tanstack/react-start**`
  and the crawled packages. These must be bundled because the compiler, the `#…` package imports and
  the virtual modules all have to apply to them.

**[verified]** `dist/server/server.js` keeps these as bare imports: `react`, `react/jsx-runtime`,
`@tanstack/react-router`, `@tanstack/react-router/ssr/server`, `@tanstack/router-core`,
`@tanstack/router-core/ssr/client`, `@tanstack/router-core/ssr/server`,
`@tanstack/router-core/isServer`, `@tanstack/history`, `seroval`, `cookie-es`,
`node:async_hooks`. Bundled in: `@tanstack/react-start` (default entries), `react-start-server`,
`react-start-client` (if reached), `start-server-core`, `start-client-core`,
`start-storage-context`, `start-fn-stubs` (compiled away), plus the app.

### 1.5 Output layout **[verified]**

```
dist/client/assets/index-<hash>.js          client entry chunk (entry name "index")
dist/client/assets/<shared>-<hash>.js       shared chunks (Rolldown named it "preload-helper" here)
dist/client/assets/<route>-<hash>.js        route split chunks (?tsr-split=…), e.g. routes-, about-, _userId-
dist/client/assets/styles-<hash>.css        CSS assets (here from `styles.css?url`)
dist/client/<public dir files>              copied (client only)
                                            (no index.html)
dist/server/server.js                       ESM; `export default { fetch }` + internal re-exports
dist/server/assets/router-<hash>.js         router entry + route tree + route files (dynamic import)
dist/server/assets/start-<hash>.js          #tanstack-start-entry (dynamic import)
dist/server/assets/empty-plugin-adapters-<hash>.js   #tanstack-start-plugin-adapters
dist/server/assets/_tanstack-start-manifest_v-<hash>.js   tanstack-start-manifest:v (dynamic import)
dist/server/assets/<route>-<hash>.js        server route split chunks (components)
dist/server/assets/<route>-<hash>.js        server function provider chunks (<file>?tss-serverfn-split)
dist/server/assets/createSsrRpc-<hash>.js, store-<hash>.js ...   shared chunks
```

The server entry's output file name is `<basename of server input without extension>.js`, so
`server.js` for both the default entry (`server.ts`) and a user `src/server.ts`. The preview
server and prerenderer import `join(serverOutDir, basename(input, extname(input)) + ".js")` and
call `.default.fetch(request)` (`SPC/vite/preview-server-plugin/plugin.js`).

Public URLs of client assets: `joinURL(publicBase, fileName)`, `publicBase` = Vite `base`
normalized to `"/…/"` (default `"/"`), so `"/assets/index-<hash>.js"`.

---

## 2. Entries

Source: `SPC/resolve-entries.js`, `SPC/planning.js: resolveStartEntryPlan`,
`NM/react-start/dist/esm/plugin/shared.js`.

Each entry is looked up in `<root>/<srcDirectory>` (default `src`) with
`exsolve.resolveModulePath("./<name>", { extensions: [".ts",".js",".mts",".mjs",".tsx",".jsx"] })`.

| entry | config key | default base name | required | fallback when absent |
|---|---|---|---|---|
| router | `router.entry` | `router` | **yes** (error `Could not resolve entry for router entry: ./router in <src>`) | none |
| start | `start.entry` | `start` | no | `react-start/dist/plugin/default-entry/start.ts` |
| client | `client.entry` | `client` | no | `react-start/dist/plugin/default-entry/client.tsx` |
| server | `server.entry` | `server` | no | `react-start/dist/plugin/default-entry/server.ts` |

Default entry files (shipped as TypeScript/TSX source; they go through the normal TS/JSX
transform and the start compiler like app code):

`default-entry/client.tsx`
```tsx
import { StrictMode, startTransition } from 'react'
import { hydrateRoot } from 'react-dom/client'
import { StartClient } from '@tanstack/react-start/client'

startTransition(() => {
  hydrateRoot(
    document,
    <StrictMode>
      <StartClient />
    </StrictMode>,
  )
})
```

`default-entry/server.ts`
```ts
import {
  createStartHandler,
  defaultStreamHandler,
  createServerEntry as createCoreServerEntry,
} from '@tanstack/react-start/server'
import type { Register } from '@tanstack/react-router'
import type { RequestHandler } from '@tanstack/react-start/server'

const fetch = createStartHandler(defaultStreamHandler)
export type ServerEntry = { fetch: RequestHandler<Register> }
export const createServerEntry: (entry: ServerEntry) => ServerEntry =
  createCoreServerEntry<Register>
export default createServerEntry({ fetch })
```
(also published compiled as `@tanstack/react-start/server-entry` →
`dist/default-entry/esm/server.js`).

`default-entry/start.ts`
```ts
export const startInstance = undefined
```

The router entry must export `getRouter()` (may be async). The start entry, when present, must
export `startInstance = createStart(() => options)`; `startInstance.getOptions()` returns
`{ requestMiddleware?, functionMiddleware?, serializationAdapters?, defaultSsr?, serverFns?: { fetch? } }`.

### 2.1 How the entries are wired at run time

Client: `client entry` → `@tanstack/react-start/client` (= `@tanstack/react-start-client`)
→ `StartClient` → `hydrateStart()` (`NM/start-client-core/dist/esm/client/hydrateStart.js`), which imports:

```js
import { startInstance } from "#tanstack-start-entry";
import { hasPluginAdapters, pluginSerializationAdapters } from "#tanstack-start-plugin-adapters";
import { getRouter } from "#tanstack-router-entry";
```

`hydrateStart`: `router = await getRouter()`; if `startInstance`: `startOptions = await getOptions()`,
`window.__TSS_START_OPTIONS__ = startOptions`, `router.options.defaultSsr = startOptions.defaultSsr`;
else `window.__TSS_START_OPTIONS__ = { serializationAdapters: [] }`. Adapters = start's + plugin
adapters + `ServerFunctionSerializationAdapter` + router's. Then
`router.update({ basepath: process.env.TSS_ROUTER_BASEPATH, serializationAdapters })` and
`hydrate(router)` unless matches already exist. In production it is `hydrateStart`; otherwise the
HMR-cached wrapper. React wrapper: `.finally(() => window.$_TSR?.h())`; `StartClient` renders
`<Await promise={hydrationPromise}>{router => <RouterProvider router={router}/>}</Await>`.

Server: `server entry` default export `{ fetch }` from `createServerEntry({ fetch: createStartHandler(defaultStreamHandler) })`.
`createStartHandler` (`NM/start-server-core/dist/esm/createStartHandler.js`) lazily loads:

```js
await Promise.all([
  import("#tanstack-router-entry"),
  import("#tanstack-start-entry"),
  import("#tanstack-start-plugin-adapters"),
])
```
and imports `tanstack-start-manifest:v` dynamically (`router-manifest.js`) and
`#tanstack-start-server-fn-resolver` statically (`getServerFnById.js`).

**[verified]** in `server.js`:
```js
async function loadEntries() {
	const [routerEntry, startEntry, pluginAdapters] = await Promise.all([
		import("./assets/router-CgbAbumg.js").then((n) => n.t),
		import("./assets/start-COmmreO7.js"),
		import("./assets/empty-plugin-adapters-CeyhLWeJ.js")
	]);
	...
```

---

## 3. Module ids: virtual modules, aliases and package imports

| id (as imported) | where it is imported | what it becomes |
|---|---|---|
| `virtual:tanstack-start-client-entry` | client build input | alias → client entry file |
| `virtual:tanstack-start-server-entry` | SSR build input (dev: module runner import) | alias → server entry file |
| `#tanstack-start-entry` | `start-client-core/client/hydrateStart.js`, `start-server-core/createStartHandler.js` | alias → start entry file (default `export const startInstance = undefined`) |
| `#tanstack-router-entry` | same two files | alias → router entry file |
| `#tanstack-start-plugin-adapters` | same two files | package.json `imports` of start-client-core / start-server-core → `dist/esm/empty-plugin-adapters.js`; overridden by a virtual module only when serialization adapters are configured (RSC) |
| `#tanstack-start-server-fn-resolver` | `start-server-core/getServerFnById.js` | **virtual** in the SSR env (resolved id `\0%23tanstack-start-server-fn-resolver`); unresolved fallback via start-server-core `imports` → `fake-start-server-fn-resolver.js` (`async function getServerFnById(){}`) |
| `tanstack-start-manifest:v` | `start-server-core/router-manifest.js` (dynamic import) | **virtual** (resolved id `\0tanstack-start-manifest:v`) |
| `virtual:tanstack-start-dev-client-entry` | dev client input | **virtual**, dev only (section 12) |
| `<file>?tss-serverfn-split` | resolver module (dynamic import) | the file's source compiled as a server function provider |
| `<file>?tsr-split=<groups>` / `?tsr-shared=1` | router code splitter | as in plain router-plugin |
| `<file>?tss-hydrate=<id>` | `<Hydrate>` transform | compiler virtual module (section 4.9) |
| `\0tanstack-start-import-protection:…` | import protection | marker/mock modules (section 9) |
| `virtual:tanstack-start-validate-server-fn-id?id=…` | dev resolver | dev only |
| `virtual:tanstack-start-plugin-adapters/{client,server}` | only with serialization adapters | `export const pluginSerializationAdapters = [...]; export const hasPluginAdapters = true` |

Package `imports` maps (they are what makes the `#` ids resolve **without** the plugin):

```json
// start-client-core/package.json
"imports": {
  "#tanstack-start-entry":           { "default": "./dist/esm/fake-entries/start.js" },  // export var startInstance = void 0
  "#tanstack-router-entry":          { "default": "./dist/esm/fake-entries/router.js" }, // export function getRouter() {}
  "#tanstack-start-plugin-adapters": { "default": "./dist/esm/empty-plugin-adapters.js" }
}
// start-server-core/package.json
"imports": {
  "#tanstack-start-server-fn-resolver": { "default": "./dist/esm/fake-start-server-fn-resolver.js" },
  "#tanstack-start-plugin-adapters":    { "default": "./dist/esm/empty-plugin-adapters.js" }
}
```

`empty-plugin-adapters.js`: `export const pluginSerializationAdapters = []; export const hasPluginAdapters = false`.

Virtual module helper (`SPC/vite/createVirtualModule.js`): resolved id = `"\0" + id.replaceAll("#", "%23")`.

### 3.1 Contents per environment

`tanstack-start-manifest:v`
* SSR build: `export const tsrStartManifest = () => (<seroval serialize(startManifest)>)` (section 7).
* client env, and SSR in dev: the empty/dev manifest
  ```js
  export const tsrStartManifest = () => ({
        routes: {
          __root__: {
            preloads: ['<clientEntry>'],
            scripts: [{ attrs: { type: 'module', async: true, src: '<clientEntry>' } }],
          },
        },
      })
  ```
  with `<clientEntry> = joinURL(publicBase, "@id", "virtual:tanstack-start-dev-client-entry")`
  (bundled-dev: `joinURL(base, "assets", "index.js")`). Never imported on the client.

`#tanstack-start-server-fn-resolver` (SSR build, `SPC/start-compiler/server-fn-resolver-module.js`,
called with `includeClientReferencedCheck: false, memoizeModules: true`) — section 5.3.

---

## 4. The start compiler

Sources: `SPC/start-compiler/{compiler,config,host,handleCreateServerFn,handleCreateMiddleware,handleCreateIsomorphicFn,handleEnvOnly,handleClientOnlyJSX,utils}.js`,
`SPC/vite/start-compiler-plugin/plugin.js`, `SPC/hydrate-when-transform.js`.

### 4.1 Where it runs

A Babel-based transform, one compiler instance per environment, `enforce: "pre"`, registered
**before** the router plugins (plugin array order in `SPC/vite/plugin.js`: config, post-build,
start compiler, import protection, start router (client tree, generator, code splitter client,
code splitter server), load-env, dev client entry, manifest, …). So on every module the start
compiler transform runs before the router code splitter's transform.

Filter:
* id matches `/\.[cm]?[tj]sx?($|\?)/` (query allowed), and does not end with `server-fn-module-lookup`;
* code matches one of the detection regexes valid for the env:

```js
KindDetectionPatterns = {
  ServerFn:      /\bcreateServerFn\b|\.\s*handler\s*\(/,
  Middleware:    /createMiddleware/,
  IsomorphicFn:  /createIsomorphicFn/,
  ServerOnlyFn:  /createServerOnlyFn/,
  ClientOnlyFn:  /createClientOnlyFn/,
  ClientOnlyJSX: /<ClientOnly|import\s*\{[^}]*\bClientOnly\b/,
}
// plus /\bHydrate\b/ for the Hydrate compiler plugin
LookupKindsPerEnv = {
  client: ["Middleware","ServerFn","IsomorphicFn","ServerOnlyFn","ClientOnlyFn"],
  server: ["ServerFn","IsomorphicFn","ServerOnlyFn","ClientOnlyFn","ClientOnlyJSX"],
}
```

**It runs on `node_modules` too.** This is load-bearing: TanStack's own packages use these
factories and rely on being compiled. **[verified]**:

| source (start-client-core) | client output | server output |
|---|---|---|
| `getStartOptions = createIsomorphicFn().client(() => window.__TSS_START_OPTIONS__).server(() => getStartContext().startOptions)` | `var getStartOptions = () => window.__TSS_START_OPTIONS__;` | `var getStartOptions = () => getStartContext().startOptions;` |
| `getStartContextServerOnly = createServerOnlyFn(getStartContext)` | `var getStartContextServerOnly = () => { throw new Error("createServerOnlyFn() functions can only be called on the server!"); };` | `var getStartContextServerOnly = getStartContext;` |
| `createCsrfMiddleware = createIsomorphicFn().server(innerCreateCsrfMiddleware)` | `() => {}` by rule 4.5 (tree-shaken from this app's client) | `var createCsrfMiddleware = innerCreateCsrfMiddleware;` |

Without this, the uncompiled stubs (`@tanstack/start-fn-stubs`: `createIsomorphicFn` returns a
function that prefers the **server** impl; `createServerOnlyFn = fn => fn`) would run server code
in the browser, and `@tanstack/start-storage-context` (`node:async_hooks`) would stay in the
client bundle. After compilation dead-code elimination drops those imports.

### 4.2 Recognising the factories

Known roots (`compiler.js: init`, `config.js: getLookupConfigurationsForEnv`), keyed by import
source and exported name:

```
@tanstack/start-fn-stubs:    createIsomorphicFn→IsomorphicFn, createServerOnlyFn→ServerOnlyFn, createClientOnlyFn→ClientOnlyFn
@tanstack/start-client-core: createServerFn→Root, createIsomorphicFn→IsomorphicFn, createServerOnlyFn→ServerOnlyFn,
                             createClientOnlyFn→ClientOnlyFn, createMiddleware→Middleware, createStart→Root
@tanstack/react-start (both envs): createServerFn→Root, createIsomorphicFn→IsomorphicFn,
                             createServerOnlyFn→ServerOnlyFn, createClientOnlyFn→ClientOnlyFn
@tanstack/react-start (client only): createMiddleware→Root, createStart→Root
@tanstack/react-router (server only): ClientOnly→ClientOnlyJSX
```

Resolution rules (`StartCompiler.resolveExprKind/resolveCalleeKind/resolveBindingKind`):

* An identifier's kind comes from its binding. An import binding is matched against the table by
  `(source, importedName)`; otherwise the compiler resolves the import (bundler `resolveId`),
  loads that module's source (bundler `load`, then parses it), and follows `export … from`,
  `export *` chains and local `const x = …` bindings, across files, with cycle guards. A
  re-export of a known root through any module is therefore recognised. A namespace import
  (`import * as S from '@tanstack/react-start'; S.createServerFn()`) is handled.
* `Root(...)` or `Builder.x(...)` evaluates to **Builder**.
* `.handler(...)` on Root/Builder → **ServerFn**.
* `.server/.client/.createMiddlewares(...)` on Root/Builder/Middleware → **Middleware** (client env only).
* `.server/.client(...)` on Root/Builder/IsomorphicFn → **IsomorphicFn**.
* `createServerOnlyFn(...)` / `createClientOnlyFn(...)` (identifier or `ns.member` call) → that kind.
* A `const x = createServerOnlyFn(fn)` binding resolves to "None" when referenced later (so calling
  `x()` is not itself a candidate).

Candidates: every CallExpression that is **not** an inner link of a method chain (a call whose
parent is a MemberExpression whose parent is a CallExpression is recorded as a chain link
instead), and that is either a method-chain call whose property is one of
`handler | server | client | createMiddlewares`, or a direct call (top level: simple
`f()`/`ns.f()` as a variable initializer at program level or under `export`; nested: callee name
is `createServerOnlyFn` / `createClientOnlyFn`). Then each candidate's kind is resolved and kept
if valid for the env. If only `ServerFn` was detected in the file, a fast path scans only the
program's top-level variable declarations.

For each candidate, the chain is walked from the outermost call inward, recording the call path
and first argument of the last-seen `.middleware`, `.validator`, `.handler`, `.server`, `.client`.

Handlers run in the order `ServerFn, Middleware, IsomorphicFn, ServerOnlyFn, ClientOnlyFn`, then
ClientOnly JSX (server), then **dead code elimination**:
`stripTypeExports(ast)` (drop type-only imports/exports) +
`babel-dead-code-elimination(ast, candidates)` where `candidates = findReferencedIdentifiers(ast)`
taken **before** the transforms. Effect: any top-level binding or import specifier that was
referenced before the transform and is no longer referenced is removed; an import declaration
left with no specifiers is removed. This is what removes `import { readCount } from "../server/store"`
from the client copy of a route file.

Parsing: `@babel/parser` with `typescript, explicitResourceManagement, importAttributes,
deprecatedImportAssert, decorators, decoratorAutoAccessors`, plus `jsx` unless the file is
plain `.ts/.mts/.cts`. Output: `@babel/generator` with source maps. If nothing changed the
transform returns `null`.

### 4.3 `createServerFn` (kind ServerFn)

Requirements (errors thrown):
* The chain must be the initializer of a variable declarator: `createServerFn must be assigned to a variable!`
* Simple identifier only: `createServerFn must be assigned to a simple identifier, not a destructuring pattern`
* `.handler(...)` must exist with an expression argument: ``createServerFn must be called with a "handler" property!``,
  `handler() must be called with an expression, not a <Type>`
* `.validator()` with no argument: `createServerFn().validator() must be called with a validator!`

Per candidate, with `X` = the variable name:
* `functionName = X + "_createServerFn_handler"`; if already used in this file,
  `incrementFunctionNameVersion`: split off a trailing `_<n>`, sanitize
  (`/[^a-zA-Z0-9_$]/g→"_"`, leading digit → `_`, leading `$` → `_$`, collapse `__+`, trim `_`),
  append `_<n+1>`.
* `baseFilename = id.split("?")[0]` (absolute path); `extractedFilename = baseFilename + "?tss-serverfn-split"`;
  `relativeFilename = path.relative(root, baseFilename)` (POSIX, e.g. `src/routes/index.tsx`).
* `functionId` (section 5.1).

Three outputs, depending on the module:

**Client env** (any module): `.validator(v)` call removed (replaced by its callee object);
the handler argument replaced by `createClientRpc("<id>")`; prepend
`import { createClientRpc } from '@tanstack/react-start/client-rpc'`. `.middleware([...])` stays.

**SSR env, caller module** (any module whose id does not contain `tss-serverfn-split`): validator
kept; handler argument replaced by `createSsrRpc("<id>")`; prepend
`import { createSsrRpc } from '@tanstack/react-start/ssr-rpc'`.

**SSR env, provider module** (`<file>?tss-serverfn-split`, reached only from the resolver):
* insert before the declaration
  `const <functionName> = createServerRpc({ id: "<id>", name: "<X>", filename: "<relativeFilename>" }, (opts) => X.__executeServer(opts));`
* change `.handler(fn)` to `.handler(<functionName>, fn)` (fn cloned);
* remove all exports from the module, keeping the declarations (`export const a = …` → `const a = …`,
  `export { … }` without declaration dropped, `export default function f(){}` → `function f(){}`;
  an anonymous default export is kept);
* append `export { <functionName>, … }`;
* in dev append `if (import.meta.hot) { import.meta.hot.accept(() => {}) } if (import.meta.webpackHot) { import.meta.webpackHot.accept(() => {}) }`;
* prepend `import { createServerRpc } from '@tanstack/react-start/server-rpc'`.
Then DCE removes everything the server functions do not use (the Route, components, …).
The router code splitter leaves provider modules alone (its lookup is by the id **with** the
query, which is not a route file).

Each non-provider compile reports `{ [functionId]: { functionName, functionId, filename: cleanId(id),
extractedFilename, isClientReferenced } }` to the shared registry (merge: `isClientReferenced` is
OR-ed). `isClientReferenced` is true in the client env, for SSR callers, or when already known.

**[verified]** Reference app, `src/routes/index.tsx`:

```tsx
const getCount = createServerFn({ method: "GET" }).handler(async () => {
  return readCount();
});
const updateCount = createServerFn({ method: "POST" })
  .validator((d: number) => d)
  .handler(async ({ data }) => {
    return addCount(data);
  });
```

Client, `index.tsx` (in the entry chunk; `updateCount` moved to the component split chunk because
only the component uses it):
```js
var getCount = createServerFn({ method: "GET" }).handler(createClientRpc("779065a854cd3c8a83fc1f6d279993fb0c1460e9882d64d8e4a9c5d1a7f37ab0"));
// index.tsx?tsr-split=component
var updateCount = createServerFn({ method: "POST" }).handler(createClientRpc("4a6fc7c69795985fd86cb3abcfb13c573bafe2093c0f67aaee631bf215685906"));
```
SSR, caller copies (route file in `router-*.js`, split component in `routes-*.js`):
```js
var getCount = createServerFn({ method: "GET" }).handler(createSsrRpc("779065a8…7ab0"));
var updateCount = createServerFn({ method: "POST" }).validator((d) => d).handler(createSsrRpc("4a6fc7c6…5906"));
```
SSR, provider `src/routes/index.tsx?tss-serverfn-split` (chunk `routes-uD2bd0xK.js`):
```js
import { i as createServerRpc, r as readCount, t as addCount } from "./store-jLWuG-YV.js";
import { t as createServerFn } from "../server.js";
// src/routes/index.tsx?tss-serverfn-split
var getCount_createServerFn_handler = createServerRpc({
	id: "779065a854cd3c8a83fc1f6d279993fb0c1460e9882d64d8e4a9c5d1a7f37ab0",
	name: "getCount",
	filename: "src/routes/index.tsx"
}, (opts) => getCount.__executeServer(opts));
var getCount = createServerFn({ method: "GET" }).handler(getCount_createServerFn_handler, async () => {
	return readCount();
});
var updateCount_createServerFn_handler = createServerRpc({
	id: "4a6fc7c69795985fd86cb3abcfb13c573bafe2093c0f67aaee631bf215685906",
	name: "updateCount",
	filename: "src/routes/index.tsx"
}, (opts) => updateCount.__executeServer(opts));
var updateCount = createServerFn({ method: "POST" }).validator((d) => d).handler(updateCount_createServerFn_handler, async ({ data }) => {
	return addCount(data);
});
export { getCount_createServerFn_handler, updateCount_createServerFn_handler };
```
The same file therefore exists as up to three SSR modules (`index.tsx`, `index.tsx?tsr-split=component`,
`index.tsx?tss-serverfn-split`) and two client modules. All compile to the same ids because the id
is derived from the query-less file name.

Runtime pieces the output relies on:

```js
// start-client-core/client-rpc/createClientRpc.js
function createClientRpc(functionId) {
  const url = process.env.TSS_SERVER_FN_BASE + functionId;
  const serverFnMeta = { id: functionId };
  const clientFn = (...args) => serverFnFetcher(url, args, getStartOptions()?.serverFns?.fetch ?? fetch);
  return Object.assign(clientFn, { url, serverFnMeta, [Symbol.for("TSS_SERVER_FUNCTION")]: true });
}
// start-server-core/createSsrRpc.js
const createSsrRpc = (functionId) => {
  const url = process.env.TSS_SERVER_FN_BASE + functionId;
  const fn = async (...args) => (await getServerFnById(functionId, { origin: "server" }))(...args);
  return Object.assign(fn, { url, serverFnMeta: { id: functionId }, [TSS_SERVER_FUNCTION]: true });
};
// start-server-core/createServerRpc.js
const createServerRpc = (serverFnMeta, splitImportFn) =>
  Object.assign(splitImportFn, { url: process.env.TSS_SERVER_FN_BASE + serverFnMeta.id, serverFnMeta, [TSS_SERVER_FUNCTION]: true });
```

`createServerFn(...).handler(extractedFn, serverFn)` (start-client-core `createServerFn.js`)
returns `async (opts) => …` that runs the function middleware chain (start's
`functionMiddleware` + `.middleware([...])` + a base middleware) in "client" mode; the base
middleware's client step calls `extractedFn({ ...ctx, context: sendContext, fetch })`. The
returned object also carries `method`, the `extractedFn` props (`url`, `serverFnMeta`, …) and, on
the server, `__executeServer(opts)` which runs the same chain in "server" mode (validators run
here, `getStartContextServerOnly()` gives the request) and returns `{ result }`, `{ result, context }`
or `{ error }`. Calls made during SSR go caller → `createSsrRpc` → resolver → provider's
`createServerRpc` wrapper → `X.__executeServer`, in process.

### 4.4 `createMiddleware` (kind Middleware, client env only)

For `createMiddleware(...)…` chains ending in `.server/.client/.createMiddlewares`: remove the
`.validator(v)` call (error if no argument: `createMiddleware().validator() must be called with a validator!`)
and the `.server(fn)` call (each replaced by its callee object). `.client(fn)` and
`.middleware([...])` stay. Server env: untouched.

```ts
// input
export const logMw = createMiddleware({ type: 'function' })
  .middleware([authMw])
  .validator(schema)
  .client(async ({ next }) => next())
  .server(async ({ next }) => { await db.log(); return next() })
// client output
export const logMw = createMiddleware({ type: 'function' })
  .middleware([authMw])
  .client(async ({ next }) => next())
// (+ DCE removes now-unused `db`, `schema` imports)
```

### 4.5 `createIsomorphicFn` (kind IsomorphicFn, both envs)

The whole chain is replaced by the argument of the env's call (`.client(fn)` in client,
`.server(fn)` in server), or by `() => {}` when that call is absent. Non-expression argument:
`createIsomorphicFn().<env>(func) must be called with a function!`.

**[verified]** `src/routes/about.tsx`:
```ts
const where = createIsomorphicFn()
  .server(() => "on the server")
  .client(() => "in the browser");
```
client: `var where = () => "in the browser";` server: `var where = () => "on the server";`
(here in the router's `about.tsx?tsr-shared=1` module, because `where` is used by both the loader
and the split component.)

### 4.6 `createServerOnlyFn` / `createClientOnlyFn` (both envs)

`createServerOnlyFn(fn)`: server → `fn`; client →
`() => { throw new Error("createServerOnlyFn() functions can only be called on the server!") }`.
`createClientOnlyFn(fn)`: client → `fn`; server →
`() => { throw new Error("createClientOnlyFn() functions can only be called on the client!") }`.
Non-expression argument: `create<Server|Client>OnlyFn() must be called with a function!`.
Works at top level and nested.

**[verified]** server `store.ts`: `var readCount = () => count; var findUser = (id) => users[id] ?? null;`
(store.ts never reaches the client: every import of it was in a server function handler, removed by DCE).

### 4.7 `<ClientOnly>` (server env only)

A JSX element whose name is a local import of `ClientOnly` **directly** from `@tanstack/react-router`
(no re-export following) loses its children and becomes self-closing:
`<ClientOnly fallback={<L/>}>{x}</ClientOnly>` → `<ClientOnly fallback={<L/>} />`. DCE then
drops bindings only the children used.

### 4.8 `createStart`, `.middleware`

`createStart` is a Root in the client env only so that chains on it resolve; the call itself is not
rewritten. `.middleware([...])` on server functions is never rewritten.

### 4.9 `<Hydrate>` (compiler plugin, both envs; selective hydration)

`SPC/hydrate-when-transform.js`. Applies when the file imports `Hydrate` from
`@tanstack/react-start` and uses `<Hydrate>`. Each boundary (not `split={false}`) gets an id
`<index base36>_<sha1(relative path).slice(0,10)>` set as prop `h`.
* Server: removes the `fallback` prop (and bindings only it used); adds `h`.
* Client: replaces the children with `<_H0 …captured/>` where
  `const _H0 = lazyRouteComponent(() => import("<abs>?tss-hydrate=<id>"), "H0")`
  (`lazyRouteComponent` imported from `@tanstack/react-router`); adds `p={_H0.preload}` if a
  `prefetch` prop exists.
* The virtual module `<abs>?tss-hydrate=<id>` exports `function H<index>({captured…}) { return <children> }`
  built from the original source with only the needed module-level bindings kept.
The client manifest collects CSS of chunks reachable by dynamic import that contain
`tss-hydrate` modules (section 7). Not used by the reference app.

---

## 5. Server function ids, provider modules and the registry

### 5.1 Function id (build)

`StartCompiler.generateFunctionId` (`compiler.js`):

```js
entryId = `${relativeFilename}--${functionName}`   // e.g. "src/routes/index.tsx--getCount_createServerFn_handler"
if cached for entryId in this compiler: reuse
else:
  id = known registry entry with same functionName && extractedFilename ? its functionId
     : user serverFns.generateFunctionId?.({ filename: relativeFilename, functionName })
     : undefined
  id ??= sha256_hex(entryId)
  while id already issued by this compiler: id = `${id}_${n}` (n = 1, 2, …)
```

**[verified]** `sha256("src/routes/index.tsx--getCount_createServerFn_handler") =
779065a854cd3c8a83fc1f6d279993fb0c1460e9882d64d8e4a9c5d1a7f37ab0`,
`sha256("src/routes/users/$userId.tsx--getUser_createServerFn_handler") =
a8229a4828a9901938eb6ac7c29bad3506ee4bd3e047562ba616d123d3d2213d`.

`root` is the Vite root (default `process.cwd()`); the relative path uses `/` separators.

Dev ids differ (section 12).

### 5.2 Registry

`serverFnsById: Record<id, { functionName, functionId, filename, extractedFilename, isClientReferenced }>`,
one object shared by the client and SSR compilers (`SPC/vite/start-compiler-plugin/plugin.js`).
The client build fills it with every server function reachable from the client; the SSR build
adds the rest as it compiles caller modules.

Timing note for Vite: the resolver module is generated when Rolldown first loads it, so a server
function that the client never references and that the SSR build only compiles after that load
would be missing. The Rsbuild adapter regenerates the resolver after all modules are compiled.
A reimplementation should generate it after the module graph is complete (and keep the client
build's ids).

### 5.3 The resolver module (`#tanstack-start-server-fn-resolver`, SSR build)

Generated by `generateServerFnResolverModule({ serverFnsById, includeClientReferencedCheck: false, memoizeModules: true })`;
entries sorted by id (string order):

```js

const manifest = {
  '<id>': {
    functionName: '<functionName>',
    importer: () => import("<absolute file path>?tss-serverfn-split")
  },
  ...
}

export async function getServerFnById(id, access) {
  const serverFnInfo = manifest[id]
  if (!serverFnInfo) {
    throw new Error('Server function info not found for ' + id)
  }

  const fnModule = serverFnInfo.module ??= await serverFnInfo.importer()
  if (!fnModule) {
    throw new Error('Server function module not resolved for ' + id)
  }
  const action = fnModule[serverFnInfo.functionName]
  if (!action) {
    throw new Error('Server function module export not resolved for serverFn ID: ' + id)
  }
  return action
}

```
(With `includeClientReferencedCheck`, used only when SSR is not the provider: each entry has
`isClientReferenced`, and `access.origin === 'client' && !isClientReferenced` throws
`Server function not accessible from client: <id>`.)

**[verified]** in `server.js`:
```js
// \0%23tanstack-start-server-fn-resolver
var manifest = {
	"4a6fc7c69795985fd86cb3abcfb13c573bafe2093c0f67aaee631bf215685906": {
		functionName: "updateCount_createServerFn_handler",
		importer: () => import("./assets/routes-uD2bd0xK.js")
	},
	"779065a854cd3c8a83fc1f6d279993fb0c1460e9882d64d8e4a9c5d1a7f37ab0": {
		functionName: "getCount_createServerFn_handler",
		importer: () => import("./assets/routes-uD2bd0xK.js")
	},
	"a8229a4828a9901938eb6ac7c29bad3506ee4bd3e047562ba616d123d3d2213d": {
		functionName: "getUser_createServerFn_handler",
		importer: () => import("./assets/_userId-y0MS8SNj.js")
	}
};
```

Each `?tss-serverfn-split` module is a dynamic-import entry point, so each file's server
functions become their own chunk (shared code such as `store.ts` and `createServerRpc` goes to
shared chunks).

### 5.4 Serialising server functions as values

`ServerFunctionSerializationAdapter` (key `"$TSS/serverfn"`, test: a function with
`Symbol.for("TSS_SERVER_FUNCTION")`): `toSerializable = ({serverFnMeta}) => ({ functionId: serverFnMeta.id })`.
Client `fromSerializable = ({functionId}) => createClientRpc(functionId)`; server
`fromSerializable` makes a function that calls `getServerFnById(functionId, { origin: "client" })`.
It is always added to the router's serialization adapters on both sides.

---

## 6. RPC protocol

Sources: `NM/start-client-core/dist/esm/client-rpc/serverFnFetcher.js`,
`NM/start-server-core/dist/esm/{createStartHandler,server-functions-handler,frame-protocol}.js`,
`NM/start-client-core/dist/esm/createCsrfMiddleware.js`. All of section 6's examples are
**[verified]** against the built server.

### 6.1 URL and routing

`TSS_SERVER_FN_BASE = joinPaths(["/", routerBasepath, serverFns.base, "/"])` = `"/_serverFn/"` by
default (`serverFns.base` default `"/_serverFn"`). URL = base + function id.

Server side: a request whose pathname starts with `TSS_SERVER_FN_BASE` is a server function
request; `serverFnId = pathname.slice(base.length).split("/")[0]` (empty → error
`Invalid server action param for serverFnId`). The pathname is not normalized for these
requests unless it contains `%` or starts with `//`.

Request middleware: `startOptions.requestMiddleware` when there is a start instance; with **no**
start instance, server function requests get a default CSRF middleware
`createCsrfMiddleware({ filter: ctx => ctx.handlerType === "serverFn" })`. Its check:
`Sec-Fetch-Site` present → must equal `"same-origin"`; else `Origin` present → must equal the
request URL's origin; else `Referer` must be same-origin; with none of the three → **403
"Forbidden"** (text/plain) unless `allowRequestsWithoutOriginCheck`. (Browsers send
`Sec-Fetch-Site`.) In non-production builds a one-time console warning is printed when the
request middleware of a server function request contains no CSRF middleware (a start instance
whose `requestMiddleware` lacks one).

### 6.2 Client request (`serverFnFetcher(url, args, fetchImpl)`)

`first = args[0]` = `{ data?, headers?, signal?, fetch?, method, context? }` (method comes from
the server fn options, default `"GET"`).

Headers: `new Headers(first.headers)`, then `x-tsr-serverFn: true`; unless the data is FormData,
`accept: application/x-tss-framed, application/x-ndjson, application/json`.

Payload = `{ data }` if `data !== undefined`, plus `context` if it has own properties (the
`sendContext` of client middleware). Serialized as
`JSON.stringify(await seroval.toJSONAsync(payload, { plugins }))`; plugins = start
serialization adapters (via `makeSerovalPlugin`) + router-core default seroval plugins.

* **GET**: append `?payload=<URLSearchParams-encoded string>` (or `&payload=` if the URL has a
  query). No payload param when there is nothing to send. FormData with GET throws
  `FormData is not supported with GET requests`.
* **POST**: body = the JSON string with `content-type: application/json`; or the FormData
  itself (context, if any, serialized and put in field `__TSS_CONTEXT`).

Example payload for `{ data: "2" }`:
```
{"t":{"t":10,"i":0,"p":{"k":["data"],"v":[{"t":1,"s":"2"}]},"o":0},"f":127,"m":[]}
```

### 6.3 Server handling (`handleServerAction`)

1. `action = await getServerFnById(id, { origin: "client" })`; unknown id → error (500 below).
2. `action.method && request.method !== action.method` → **405**, body
   `expected <M> method. Got <m>`, header `Allow: <M>`.
3. Input: `multipart/form-data` or `application/x-www-form-urlencoded` → `{ data: formData,
   method, context? }` (context from `__TSS_CONTEXT`, seroval `fromJSON`). Else GET → `payload`
   query param (max 1,000,000 chars, else `Payload too large`), POST with `application/json` →
   `request.json()`; then `fromJSON(json, { plugins })` → `action({ data: payload?.data,
   context: payload?.context, method })`.
4. `res` is `{ result }`, `{ result, context }` or `{ error }`.
5. If the request lacks `x-tsr-serverFn: true` and the unwrapped value is a Response, `null` or
   a primitive, that value is returned as the response as is (plain HTTP use).
6. Unwrapped Response: thrown → returned with `x-tss-raw: thrown` (redirects are returned as is);
   redirect → returned as is; other → returned with `x-tss-raw: true`.
7. Otherwise serialize **the whole `res` object** with `seroval.toCrossJSONStream` (plugins:
   RawStream RPC plugin + adapters). If it completes synchronously in one record without raw
   streams: `200`, `content-type: application/json`, `x-tss-serialized: true`, body = that
   cross-JSON record. Else a framed stream (6.5).
8. A thrown error (outside the function's own `{error}`): `Response` → returned; else
   `createServerFnErrorResponse`: notFound → 404 JSON (below); other → status from the error
   (default 500), `content-type: application/json`, `x-tss-serialized: true`, body
   `toCrossJSONAsync({ error })`.

Observed responses:

```
GET /_serverFn/779065a8…  (getCount)                → 200  application/json  x-tss-serialized: true
{"t":10,"i":0,"p":{"k":["result"],"v":[{"t":0,"s":0}]},"o":0}

POST /_serverFn/4a6fc7c6… body {data:1}             → 200
{"t":10,"i":0,"p":{"k":["result"],"v":[{"t":0,"s":1}]},"o":0}

GET /_serverFn/a8229a48…?payload=<{data:"2"}>       → 200
{"t":10,"i":0,"p":{"k":["result"],"v":[{"t":10,"i":1,"p":{"k":["id","name"],"v":[{"t":1,"s":"2"},{"t":1,"s":"Grace"}]},"o":0}]},"o":0}

handler throws notFound() (payload {data:"9"})      → 200  (the error travels inside the result)
{"t":10,"i":0,"p":{"k":["error"],"v":[{"t":10,"i":1,"p":{"k":["isNotFound"],"v":[{"t":2,"s":2}]},"o":0}]},"o":0}

GET on a POST function                              → 405  Allow: POST   "expected POST method. Got GET"

unknown id                                          → 500  application/json  x-tss-serialized: true
{"t":10,"i":0,"p":{"k":["error"],"v":[{"t":25,"i":1,"s":{"message":{"t":1,"s":"Server function info not found for deadbeef"}},"c":"$TSR/Error"}]},"o":0}

no Sec-Fetch-Site / Origin / Referer                → 403  text/plain  "Forbidden"
```

Redirects: a redirect thrown by a server function (or by request middleware) on a request with
`x-tsr-serverFn: true` becomes `content-type: application/json`, no `location`, body =
`JSON.stringify({ ...redirect.options without headers, isSerializedRedirect: true })`, status
200 unless `setResponseStatus` set one (`handleRedirectResponse` → `createFinalizedResponse`).
Plain JSON results (status 200) likewise take a status set with `setResponseStatus`. Without that header, a real HTTP redirect.
notFound thrown outside the function: **404**, `application/json`, body `JSON.stringify(notFound minus headers)`.

### 6.4 Client response handling (`getResponse`)

* `x-tss-raw: true` → return the Response; `x-tss-raw: thrown` → throw it.
* No content-type → invariant error.
* `x-tss-serialized` present: framed (`application/x-tss-framed`, version param must be 1) →
  frame decoder; `application/json` → `seroval.fromCrossJSON(await res.json(), { plugins })`.
* Otherwise `application/json` → if `parseRedirect(json)` → throw redirect; if `isNotFound(json)`
  → throw it; else return the JSON.
* Otherwise `!res.ok` → `throw new Error(await res.text())`; else return the Response.

The decoded `{ result | error | context }` goes back through the client middleware chain;
`"error" in result` → thrown (`parseRedirect(error) ?? error`).

### 6.5 Framed protocol (streams / RawStream)

`content-type: application/x-tss-framed; v=1`, `x-tss-serialized: true`. Body = sequence of
frames `[type:u8][streamId:u32 BE][length:u32 BE][payload]`; types `0 JSON` (streamId must be 0;
payload = one JSON record of a cross-JSON stream), `1 CHUNK`, `2 END` (length 0), `3 ERROR`
(payload = UTF-8 message, ≤ 4096 code units). Limits: payload ≤ 16 MiB, ≤ 1024 raw streams,
≤ 128 MiB unread per raw stream. The first JSON record is the result; later records continue
the seroval stream (promises, async iterables).

---

## 7. The start manifest

Sources: `SPC/vite/start-manifest-plugin/{plugin,normalized-client-build}.js`,
`SPC/start-manifest-plugin/manifestBuilder.js`,
`SPC/start-router-plugin/generator-plugins/routes-manifest-plugin.js`,
`NM/start-server-core/dist/esm/{router-manifest,finalManifest,transformAssetUrls}.js`.

### 7.1 Inputs

**Routes manifest** (`globalThis.TSS_ROUTES_MANIFEST`, written by a generator plugin on every
route tree change):

```js
{
  __root__: { filePath: rootRouteNode.fullPath, children: routeTree.map(n => n.routePath) },
  [node.routePath]: { filePath: node.fullPath, children: node.children?.map(c => c.routePath) },  // every routeNode
}
```
`filePath` is the absolute route file path; keys are the generator's `routePath`, which is the
route id used at run time.

**Client build** (captured at the client's `generateBundle`): for each chunk
`{ fileName, isEntry, imports, dynamicImports, css: viteMetadata.importedCss,
routeFilePaths, hydrationIds }`:
* `routeFilePaths` = for each module id in the chunk with a `tsr-split` query parameter,
  the id without query (deduplicated). This is how a chunk is tied to a route file.
* `hydrationIds` = values of `tss-hydrate` query params.
* exactly one entry chunk (else `multiple entries detected` / `No entry file found`).

### 7.2 Algorithm (`buildStartManifest`)

```
assetPath(f)        = joinURL(publicBase, f)
closure(chunk)      = transitive static `imports`, DFS (fileNames in discovery order; chunks dependencies-first)
preloads(chunk)     = [assetPath(chunk.fileName), ...closure(chunk).fileNames.map(assetPath)]
css(chunk)          = for c in closure(chunk).dependenciesFirst (chunk itself last): c.css (deduped) → assetPath

routes = {}
for (routeId, route) in routesManifest:
  if !route.filePath: root → routes[root] = {...route}; else error "expected filePath to be set for <id>"
  chunks = chunks whose routeFilePaths contain route.filePath
  routes[routeId] = {...route}            // keeps filePath, children
  for chunk in chunks:
    route.css      ∪= css(chunk)          // deduped by href+crossOrigin
    route.preloads ∪= preloads(chunk)
    if routeId != root: add css of dynamically imported chunks with hydrationIds reachable from chunk
root = routes.__root__ ?? {}
(root route's own chunks: hydration css only)
root.css ∪= css(entryChunk); root.preloads ∪= preloads(entryChunk)
additionalRouteAssets: with build.cssCodeSplit === false, root gets the "style.css" asset as css
root.scripts += [{ attrs: { type: "module", async: true, src: assetPath(entry.fileName) } }]
   (scriptFormat "iife" — not used by Vite — would add the entry's imports first, without type)
dedupe: walk from root through `children`; drop a preload/script/stylesheet already present in an ancestor
delete routes that end up with no scripts, css and preloads
result = { routes } (+ inlineCss data when server.build.inlineCss is enabled)
```

The module text is `export const tsrStartManifest = () => (<seroval.serialize(result)>)`.

**[verified]** `dist/server/assets/_tanstack-start-manifest_v-*.js` (unminified build):
```js
// \0tanstack-start-manifest:v
var tsrStartManifest = () => ({ routes: {
	__root__: {
		filePath: "/…/tanstack-start/src/routes/__root.tsx",
		children: ["/", "/about", "/users/$userId"],
		preloads: ["/assets/index-Cb1SIEMo.js", "/assets/preload-helper-CpTWwY25.js"],
		scripts: [{ attrs: { type: "module", async: !0, src: "/assets/index-Cb1SIEMo.js" } }]
	},
	"/": {
		filePath: "/…/src/routes/index.tsx",
		children: void 0,
		preloads: ["/assets/routes-3INoZYTh.js"]
	},
	"/about": { filePath: "/…/src/routes/about.tsx", children: void 0, preloads: ["/assets/about-DHD4cyVb.js"] },
	"/users/$userId": { filePath: "/…/src/routes/users/$userId.tsx", children: void 0, preloads: ["/assets/_userId-CvEEv9eK.js"] }
} });
export { tsrStartManifest };
```
(`routes-3INoZYTh.js` statically imports the entry and the shared chunk; those were deduped
against the root.) No `css` entries here because the app's only stylesheet is imported with
`?url` and linked from the root route's `head()`, not imported as a side effect.

### 7.3 Use at run time

`getStartManifest(matchedRoutes)` imports `tanstack-start-manifest:v`, calls `tsrStartManifest()`,
and keeps per route only non-empty `preloads`, `scripts`, `css` (drops `filePath`, `children`),
plus `scriptFormat` / `inlineCss`. In production the result is computed once and cached
(`createCachedBaseManifestLoader`), then `buildManifest` (or `transformManifestAssets` when the
handler has `transformAssets`) gives the final manifest, attached to the router with
`attachRouterServerSsrUtils({ router, manifest })`.

What the router does with it (`react-router` `HeadContent`/`Scripts`, router-core SSR) for the
**matched** routes **[verified]**:
* `<head>`: route `head()` meta/links/title, then manifest `css` as
  `<link rel="stylesheet" …>`, then each matched route's `preloads` as
  `<link rel="modulepreload" href="…" fetchPriority="low"/>`.
* `<body>` at `<Scripts/>`: the dehydration script
  `<script data-tsr-stream-part="">(self.$R=self.$R||{})["tsr"]=[];self.$_TSR={…};$_TSR.router=($R=>$R[0]={manifest:…,matches:[…]})($R["tsr"]);$_TSR.e();…</script>`
  (the manifest subset for the matched routes and the dehydrated matches, loader data included),
  then the manifest `scripts` → `<script type="module" async="" src="/assets/index-….js"></script>`,
  then `<script>document.currentScript.remove();/*$tsr-stream-boundary*/</script>`.

Example `GET /` (200, `content-type: text/html; charset=utf-8`):
```html
<!DOCTYPE html><html><head><meta charSet="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><link rel="stylesheet" href="/assets/styles-BH6gdvjd.css" data-precedence="default"/><title>TanStack Start app</title><link rel="modulepreload" href="/assets/index-ZYkxwzTt.js" fetchPriority="low"/><link rel="modulepreload" href="/assets/preload-helper-X4Mg6kI_.js" fetchPriority="low"/><link rel="modulepreload" href="/assets/routes-U7u8sWPM.js" fetchPriority="low"/></head><body>…<script data-tsr-stream-part="">…$_TSR.router=($R=>$R[0]={manifest:$R[1]={routes:$R[2]={__root__:$R[3]={preloads:$R[4]=["/assets/index-ZYkxwzTt.js","/assets/preload-helper-X4Mg6kI_.js"],scripts:$R[5]=[$R[6]={attrs:$R[7]={type:"module",async:!0,src:"/assets/index-ZYkxwzTt.js"}}]},"/":$R[8]={preloads:$R[9]=["/assets/routes-U7u8sWPM.js"]}}},matches:$R[10]=[…]})($R["tsr"]);$_TSR.e();…</script><script type="module" async="" src="/assets/index-ZYkxwzTt.js"></script><script>document.currentScript.remove();/*$tsr-stream-boundary*/</script></body></html>
```
`GET /nope` → 404 with the root `notFoundComponent`; a request whose `Accept` has neither
`text/html` nor `*/*` → 406 `{"error":"Only HTML requests are supported here"}`.

---

## 8. Server request flow (`createStartHandler`)

Per request (`withStartRequest` sets an AsyncLocalStorage event):
1. Normalize the URL (protocol-relative `//x` → 308 redirect) except for server fn paths.
2. Load entries (once). `startOptions = startInstance ? await startInstance.getOptions() : {}`.
   Serialization adapters = start's + plugin adapters + `ServerFunctionSerializationAdapter`.
3. Router per request: `getRouter()`, then `router.update({ history: createServerHistory(path+search+hash),
   isShell, isPrerendering, origin, defaultSsr, serializationAdapters, basepath: TSS_ROUTER_BASEPATH || "/" })`.
4. Server fn request → request middleware → `runWithStartContext({…, contextAfterGlobalMiddlewares}, handleServerAction)`.
5. Otherwise `handleServerRoutes`: route `server.middleware`, then for an exact match with
   `server.handlers` (`GET`/`POST`/…/`ANY`, `HEAD` falls back to `GET`/`ANY`): the handler runs;
   if the route has no `component` it is terminal, else it may call `next()` to defer to the app
   router. The app router: check `Accept`, resolve the manifest, `router.load()`, redirect →
   response, `router.serverSsr.dehydrate()`, headers = `content-type: text/html; charset=utf-8`
   merged with matches' `headers()`, then the handler callback (`defaultStreamHandler` →
   `renderRouterToStream({ request, router, responseHeaders, children: <StartServer router/> })`,
   `StartServer` = `<RouterProvider router/>`).
6. HEAD strips the body. Errors in `createServerEntry`'s `fetch` → `handleStartError`.

Run-time env reads that stay in the build: `process.env.TSS_PRERENDERING`, `process.env.TSS_SHELL`
(prerender sets them; header `X-TSS_SHELL: true` asks for the SPA shell while prerendering).

---

## 9. Import protection

Sources: `SPC/vite/import-protection-plugin/plugin.js`, `SPC/import-protection/*`.

Enabled by default (`importProtection.enabled === false` disables). Behavior: build `"error"`,
dev `"mock"` (configurable per mode). Applies in both environments, to importers inside
`srcDirectory` (or matching `include`, minus `exclude`/`ignoreImporters`).

Default rules (`defaults.js`):

| env | denied specifiers | denied files (relative to root, picomatch, `dot: true`) | excluded files |
|---|---|---|---|
| client | `@tanstack/react-start/server`, `@tanstack/solid-start/server`, `@tanstack/vue-start/server` | `**/*.server.*` | `**/node_modules/**` |
| server | — | `**/*.client.*` | `**/node_modules/**` |

User `client.specifiers` are added to the defaults; user `files`/`excludeFiles` and
`server.specifiers` replace them.

Markers: importing `@tanstack/react-start/server-only` marks the importing file server-only;
`@tanstack/react-start/client-only` marks it client-only (those package files are empty). The
marker import resolves to `\0tanstack-start-import-protection:marker:server|client` (`export {}`).
A file with both → error
`[import-protection] File "<rel>" has both server-only and client-only markers. This is not allowed.`
Importing a marked file from the other environment is a violation.

Build mode mechanics:
* `resolveId` of a denied import returns a **mock edge module**
  `\0tanstack-start-import-protection:mock-edge:<base64url({exports, runtimeId})>` that
  re-exports the denied module's named exports from a Proxy-based mock
  (`tanstack-start-import-protection:mock:build:<n>`). A denied file is also replaced
  by a self-contained mock when it is itself transformed in the wrong env.
* The violation is **deferred**. At `generateBundle`, a violation counts only if its mock module
  (or, for markers, the importer) survived into a chunk, i.e. it was not removed by the
  compiler's DCE or tree shaking. So a server-only import used only inside a `createServerFn`
  handler is fine on the client.
* A surviving violation in `"error"` mode fails the build with:

```

[import-protection] Import denied in client environment

  Denied by file pattern: **/*.server.*          (or: Denied by specifier pattern: <p> / Denied by marker: module is restricted to the opposite environment)
  Importer: src/routes/x.tsx:3:1
  Import: "../db.server"
  Resolved: src/db.server.ts

  Trace:
    1. <entry> (entry)
    2. src/routes/x.tsx:3:1 (import "../db.server")

  Code:
  <code frame>

  src/routes/x.tsx:3:1

  Suggestions:
    - Use createServerFn().handler(() => ...) to keep the logic on the server and call it from the client via an RPC bridge
    - Use createServerOnlyFn(() => ...) to mark it as server-only (it will throw if accidentally called from the client)
    - Use createIsomorphicFn().client(() => ...).server(() => ...) to provide separate client and server implementations
    - Move the server-only import out of this file into a separate .server.ts module that is not imported by any client code

```
(server env suggestions: `createClientOnlyFn`, `createIsomorphicFn`, move into `.client.ts`, plus
"Wrap the JSX in <ClientOnly fallback={<Loading />}>…</ClientOnly>" when the snippet looks like JSX.)
In `"mock"` mode the build warns instead and keeps the mock. `onViolation(info)` returning
`false` suppresses a violation.

The reference app has no `.server.*`/`.client.*` files or markers; `src/server/store.ts` is
protected only by the compiler (all its importers are server function handlers).

---

## 10. The router plugin inside Start

Sources: `SPC/vite/start-router-plugin/plugin.js`, `SPC/start-router-plugin/*`,
`SPC/schema.js`, `NM/router-plugin/dist/esm/core/router-code-splitter-plugin.js`.

* Router options: the Start config's `router` key = router-plugin config **minus**
  `autoCodeSplitting` and `target` (not settable), `routesDirectory` default `<src>/routes`,
  `generatedRouteTree` default `<src>/routeTree.gen.ts`, `target` forced to `"react"`.
* **Code splitting is always on**, in both environments, through two code-splitter instances
  (the `autoCodeSplitting` flag is not consulted):
  * client: `codeSplittingOptions = { ...user, deleteNodes: ["ssr","server","headers"], addHmr: true }`
    (HMR code only when not production);
  * ssr: `{ ...user, addHmr: false }`, no deleteNodes: the server keeps `ssr`, `server`, `headers`
    route options, and route components are still split into lazily imported chunks
    **[verified]** (`dist/server/assets/routes-*.js`, `about-*.js`, `_userId-*.js` contain the components;
    the route file uses `lazyRouteComponent(() => import("./routes-….js"), "component")`).
  Default groupings are the router-plugin's (`defaultCodeSplitGroupings`), and
  `codeSplittingOptions.defaultBehavior`/`splitBehavior` apply.
* Generator config (`startGeneratorConfig`): `{ ...router, target: "react", routeTreeFileFooter, plugins }`
  with plugins = client-tree plugin, routes-manifest plugin, prerender-routes plugin (only when
  `prerender.enabled === true`), then the user's.
* Route tree footer appended to `routeTree.gen.ts` (paths relative to the tree file):
  ```ts
  import type { getRouter } from './router.tsx'
  import type { createStart } from '@tanstack/react-start'      // or: import type { startInstance } from './start.ts'
  declare module '@tanstack/react-start' {
    interface Register {
      ssr: true
      router: Awaited<ReturnType<typeof getRouter>>
      // with a start file:  config: Awaited<ReturnType<typeof startInstance.getOptions>>
    }
  }
  ```
  followed by the user's `routeTreeFileFooter` lines. **[verified]** in `src/routeTree.gen.ts`.
* **Client route tree**: in the client env, a `load` hook for the generated tree path returns
  generated code, not the file: the crawl result with `pruneServerOnlySubtrees` applied (a route
  whose `createFileRoute` options have only the `server` key, with all children also pruned, is
  removed) and `{ disableTypes: true, enableRouteTreeFormatting: false, routeTreeFileHeader: [],
  routeTreeFileFooter: [] }`. **[verified]** client bundle has
  `routeTree = Route$3._addFileChildren(rootRouteChildren)` while the server (file on disk) has
  `._addFileChildren(rootRouteChildren)._addFileTypes()`.
* The SSR build uses `routeTree.gen.ts` from disk (server-only routes included).
* Dev: when a route switches between server-only and not, the client tree module is invalidated
  and a full reload sent.

---

## 11. Configuration, defines, assets, post-build

### 11.1 Defines (`createViteDefineConfig`), each as both `process.env.X` and `import.meta.env.X`

| key | value (build, defaults) |
|---|---|
| `TSS_SERVER_FN_BASE` | `"/_serverFn/"` |
| `TSS_ROUTER_BASEPATH` | `""` (router basepath = `base` with slashes trimmed; `"/"` → `""`) |
| `TSS_SHELL` | only in dev: `spa.enabled ? "true" : "false"` |
| `TSS_DEV_SERVER` | `"false"` (`"true"` in dev) |
| `TSS_DEV_SSR_STYLES_ENABLED` | `"true"` (dev.ssrStyles.enabled) |
| `TSS_DEV_SSR_STYLES_BASEPATH` | `dev.ssrStyles.basepath ?? publicBase` (`"/"`) |
| `TSS_INLINE_CSS_ENABLED` | `"false"` (`server.build.inlineCss`) |
| `TSS_DISABLE_CSRF_MIDDLEWARE_WARNING` | `"false"` |
| `process.env.NODE_ENV` | build with `server.build.staticNodeEnv` (default true): `JSON.stringify(process.env.NODE_ENV \|\| mode \|\| "production")` |

These apply to both environments. **[verified]** client code has no `process.env`
left; `server.js` keeps only `process.env.TSS_PRERENDERING` and `process.env.TSS_SHELL`. The
server reads `process.env.TSS_ROUTER_BASEPATH || "/"`, so the empty string becomes `/` there.
Vite's own `import.meta.env.*` (`SSR`, `DEV`, `PROD`, `MODE`, `BASE_URL`, `VITE_*`) apply as usual.

`loadEnvPlugin`: at `configResolved`, `Object.assign(process.env, loadEnv(mode, root, ""))`
(every `.env*` key, no prefix filter, into the **build process** env).

### 11.2 Start options (defaults, `SPC/schema.js`)

```
srcDirectory: "src"
start.entry / router.entry / client.entry / server.entry: (resolved as in section 2)
router.basepath: derived from Vite base
client.base: "/_build"                 (parsed, unused by the Vite plugin)
server.build.staticNodeEnv: true
server.build.inlineCss: false          ({enabled, transformAssets})
serverFns.base: "/_serverFn", disableCsrfMiddlewareWarning: false, generateFunctionId?: ({filename, functionName}) => string
pages: []
sitemap: undefined                     (so no sitemap)
prerender: undefined                   (enabled only if set, or any page has prerender.enabled)
spa: undefined                         (when given: enabled true, maskPath "/", prerender.outputPath "/_shell", crawlLinks false)
dev.ssrStyles: { enabled: true }
importProtection: see section 9
```

### 11.3 Post-build (`SPC/post-build.js`)

Runs after both builds. With defaults nothing happens. If prerender is enabled: start Vite
preview (imports `dist/server/server.js`), request each page (`pages`, else `/`, plus
auto-discovered static paths with a component when `autoStaticPathsDiscovery`), write HTML to the
client out dir (`<path>/index.html`), crawl `<a href>` links. SPA mode adds the mask path page,
prerendered with header `X-TSS_SHELL: true` to `/_shell.html`. Sitemap written to the client out
dir when `sitemap.enabled`.

### 11.4 `?url` and CSS

`import appCss from "../styles.css?url"` is plain Vite: the client build emits the processed CSS
as `assets/styles-<hash>.css` and the import evaluates to `"/assets/styles-<hash>.css"`; the SSR
build evaluates to the **same** URL string without emitting the file **[verified]**
(`var styles_default = "/assets/styles-BH6gdvjd.css";` in both). A reimplementation must give the
server the client's URL. CSS imported for side effects becomes the chunk's `importedCss` and ends
up in the start manifest `css` lists (section 7).

Vite also wraps client dynamic imports in its preload helper
(`__vitePreload(() => import("./routes-….js"), __vite__mapDeps([0,1]))`), which preloads the
chunk's static deps and CSS when a lazy route loads. That is Vite behaviour, not Start.

---

## 12. Dev mode (for later)

* Client input `virtual:tanstack-start-dev-client-entry`:
  ```js
  import { injectIntoGlobalHook } from "<resolved /@react-refresh>";
  injectIntoGlobalHook(window);
  window.$RefreshReg$ = () => {};
  window.$RefreshSig$ = () => (type) => type;
  window.__vite_plugin_react_preamble_installed__ = true;
  await import("<client entry path>")
  ```
  (plain `import "<client entry>"` when not React or HMR is off). Error if `/@react-refresh`
  cannot be resolved.
* Dev manifest: root `preloads: ["/@id/virtual:tanstack-start-dev-client-entry"]`, script
  `{ type: "module", async: true, src: same }`; plus a CSS link
  `buildDevStylesUrl(TSS_DEV_SSR_STYLES_BASEPATH, matchedRouteIds)` with `DEV_STYLES_ATTR`, served by a
  middleware at `…/@tanstack-start/styles.css?routes=<ids>` that collects the CSS reachable from those
  route files (via `TSS_ROUTES_MANIFEST` filePaths) to avoid a flash of unstyled content.
* SSR: a Vite middleware (installed after Vite's own) handles every other request with
  `(await serverEnv.runner.import("virtual:tanstack-start-server-entry")).default.fetch(webRequest)`;
  errors → 500 with Vite's error overlay HTML (JSON body when the request was JSON).
* Dev function ids: `base64url(JSON.stringify({ file, export: functionName }))` where `file` is
  the provider module specifier: `"/" + path relative to root + "?tss-serverfn-split"` (or
  `/@fs/<abs>?…` outside root). Dev resolver:
  ```js
  export async function getServerFnById(id, _access) {
    const validateIdImport = "virtual:tanstack-start-validate-server-fn-id" + '?id=' + id
    await import(/* @vite-ignore */ '/@id/__x00__' + validateIdImport)
    const decoded = Buffer.from(id, 'base64url').toString('utf8')
    const devServerFn = JSON.parse(decoded)
    const mod = await import(/* @vite-ignore */ devServerFn.file)
    return mod[devServerFn.export]
  }
  ```
  The validator module errors `Invalid server function ID: <id>` unless the id is in the registry
  or compiling `<file>?server-fn-module-lookup` registers it (prevents importing arbitrary files).
* The compiler's cross-module resolution loads modules with the `?server-fn-module-lookup` flag
  in dev; HMR invalidates compiler caches, provider modules, and transitive importers on the server.
* Provider modules accept HMR (`import.meta.hot.accept(() => {})`).
* `hydrateStart` is cached across HMR in `import.meta.hot.data["tss-hydrate-start-promise"]`.
* Import protection defaults to `"mock"` in dev; denied imports in the client are rewritten to
  `/@id/__x00__tanstack-start-import-protection:mock-edge:…` modules that log
  `[import-protection] Mocked import used in dev client …` on use.

---

## 13. Implementation checklist for another bundler

1. Resolve entries (section 2); alias `#tanstack-router-entry`, `#tanstack-start-entry`
   (default start entry if none); client input = client entry; server input = server entry.
2. Honour package.json `imports` (`#tanstack-start-plugin-adapters` → empty adapters) and
   override `#tanstack-start-server-fn-resolver` and `tanstack-start-manifest:v` in the server build.
3. Client: browser conditions, bundle all. Server: node conditions, ESM output, externalize
   node_modules except `@tanstack/start*`, `@tanstack/react-start*` (and packages that peer-depend
   on them).
4. Run the start compiler on every JS/TS module (node_modules included) whose code matches the
   detection regexes, before the router code splitter, per environment rules (section 4),
   followed by the same reference-based DCE.
5. Function ids: `sha256_hex(relPath + "--" + varName + "_createServerFn_handler")`, collision
   suffixes as in 5.1; ids must be identical between client and server builds.
6. Server build: make each file with server functions reachable as
   `<abs>?tss-serverfn-split` through the resolver's dynamic imports and compile it in provider
   mode; generate the resolver after all modules are known.
7. Router: generate the tree with the Start footer; client gets the pruned, type-free tree;
   code-split both envs (client deletes `ssr/server/headers`).
8. Build the start manifest from the client chunk graph and `TSS_ROUTES_MANIFEST`
   (section 7) and serialize it with seroval into the manifest module.
9. Defines (11.1), `?url` URLs shared with the client build, import protection (section 9).
10. Output: `dist/client/assets/*` (+ public), `dist/server/server.js` exporting default `{ fetch }`,
    chunks in `dist/server/assets/`.

---

## Appendix A. Reference app outputs (unminified, `vite build --minify false`)

Client entry chunk tail (app part of `assets/index-<hash>.js`):
```js
// src/routes/index.tsx
var $$splitComponentImporter$2 = () => __vitePreload(() => import("./routes-3INoZYTh.js"), __vite__mapDeps([0,1]));
var getCount = createServerFn({ method: "GET" }).handler(createClientRpc("779065a854cd3c8a83fc1f6d279993fb0c1460e9882d64d8e4a9c5d1a7f37ab0"));
var Route$2 = createFileRoute("/")({
	loader: async () => await getCount(),
	component: lazyRouteComponent($$splitComponentImporter$2, "component")
});
// src/routes/about.tsx?tsr-shared=1
var where = () => "in the browser";
// src/routes/about.tsx
var $$splitComponentImporter$1 = () => __vitePreload(() => import("./about-DHD4cyVb.js"), __vite__mapDeps([2,1]));
var Route$1 = createFileRoute("/about")({
	loader: () => where(),
	component: lazyRouteComponent($$splitComponentImporter$1, "component")
});
// src/routes/users/$userId.tsx
var $$splitComponentImporter = () => __vitePreload(() => import("./_userId-CvEEv9eK.js"), __vite__mapDeps([3,1]));
var getUser = createServerFn({ method: "GET" }).handler(createClientRpc("a8229a4828a9901938eb6ac7c29bad3506ee4bd3e047562ba616d123d3d2213d"));
var Route = createFileRoute("/users/$userId")({
	loader: ({ params }) => getUser({ data: params.userId }),
	component: lazyRouteComponent($$splitComponentImporter, "component")
});
// src/routeTree.gen.ts
var rootRouteChildren = {
	IndexRoute: Route$2.update({ id: "/", path: "/", getParentRoute: () => Route$3 }),
	AboutRoute: Route$1.update({ id: "/about", path: "/about", getParentRoute: () => Route$3 }),
	UsersUserIdRoute: Route.update({ id: "/users/$userId", path: "/users/$userId", getParentRoute: () => Route$3 })
};
var routeTree = Route$3._addFileChildren(rootRouteChildren);
// src/router.tsx
function getRouter() { return createRouter({ routeTree, scrollRestoration: true, defaultPreload: "intent" }); }
// node_modules/@tanstack/start-client-core/dist/esm/client/hydrateStart.js
async function hydrateStart() {
	const router = await getRouter();
	let serializationAdapters = [];
	window.__TSS_START_OPTIONS__ = { serializationAdapters };
	serializationAdapters.push(ServerFunctionSerializationAdapter);
	if (router.options.serializationAdapters) serializationAdapters.push(...router.options.serializationAdapters);
	router.update({ basepath: "", serializationAdapters });
	if (!router.stores.ids.get().length) await hydrate(router);
	return router;
}
var exportedHydrateStart = hydrateStart;
// node_modules/@tanstack/react-start-client/dist/esm/hydrateStart.js
function hydrateStart$1() { return exportedHydrateStart().finally(() => window.$_TSR?.h()); }
// node_modules/@tanstack/react-start-client/dist/esm/StartClient.js
var hydrationPromise;
function StartClient() {
	if (!hydrationPromise) hydrationPromise = hydrateStart$1();
	return jsx(Await, { promise: hydrationPromise, children: (router) => jsx(RouterProvider, { router }) });
}
// node_modules/@tanstack/react-start/dist/plugin/default-entry/client.tsx
(0, import_react.startTransition)(() => {
	(0, import_client.hydrateRoot)(document, jsx(import_react.StrictMode, { children: jsx(StartClient, {}) }));
});
```
(`startInstance` is `undefined`, so the `if (startInstance)` branch and the plugin-adapter push
were folded away.)

Server `assets/router-<hash>.js` (route files + tree + router entry):
```js
import { t as createSsrRpc } from "./createSsrRpc-DMOxS5bQ.js";
import { t as createServerFn } from "../server.js";
import { HeadContent, Link, Outlet, Scripts, createFileRoute, createRootRoute, createRouter, lazyRouteComponent } from "@tanstack/react-router";
// src/styles.css?url
var styles_default = "/assets/styles-BXJSEAh8.css";
// src/routes/__root.tsx … (unchanged root route)
// src/routes/index.tsx
var $$splitComponentImporter$2 = () => import("./routes-DS7v93Wa.js");
var getCount = createServerFn({ method: "GET" }).handler(createSsrRpc("779065a8…7ab0"));
var Route$2 = createFileRoute("/")({ loader: async () => await getCount(), component: lazyRouteComponent($$splitComponentImporter$2, "component") });
// src/routes/about.tsx?tsr-shared=1
var where = () => "on the server";
// src/routes/users/$userId.tsx
var getUser = createServerFn({ method: "GET" }).validator((id) => id).handler(createSsrRpc("a8229a48…213d"));
// src/routeTree.gen.ts
var routeTree = Route$3._addFileChildren(rootRouteChildren)._addFileTypes();
// src/router.tsx
var router_exports = __exportAll({ getRouter: () => getRouter });
function getRouter() { … }
```

Server provider `assets/_userId-<hash>.js` (`src/routes/users/$userId.tsx?tss-serverfn-split`):
```js
import { i as createServerRpc, n as findUser } from "./store-jLWuG-YV.js";
import { t as createServerFn } from "../server.js";
import { notFound } from "@tanstack/react-router";
var getUser_createServerFn_handler = createServerRpc({
	id: "a8229a4828a9901938eb6ac7c29bad3506ee4bd3e047562ba616d123d3d2213d",
	name: "getUser",
	filename: "src/routes/users/$userId.tsx"
}, (opts) => getUser.__executeServer(opts));
var getUser = createServerFn({ method: "GET" }).validator((id) => id).handler(getUser_createServerFn_handler, async ({ data }) => {
	const user = findUser(data);
	if (!user) throw notFound();
	return user;
});
export { getUser_createServerFn_handler };
```

`server.js` module order (bundled modules, as commented by Rolldown): react-start-server
StartServer, defaultStreamHandler; start-server-core headers, internal-request-response,
constants, router-manifest; `\0%23tanstack-start-server-fn-resolver`; start-client-core constants;
start-storage-context; start-client-core getStartOptions, getDefaultSerovalPlugins;
start-server-core frame-protocol; start-client-core safeObjectMerge, getStartContextServerOnly,
createServerFn, createMiddleware, createCsrfMiddleware; start-server-core
server-functions-handler, early-hints, transformAssetUrls, inlineCss, finalManifest,
ServerFunctionSerializationAdapter, createStartHandler; react-start default-entry/server.ts.
Exports: `export { createServerEntry, server_default as default, TSS_SERVER_FUNCTION as n, getServerFnById as r, createServerFn as t };`
