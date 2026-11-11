#!/usr/bin/env python3
"""Fragments on real libraries: what each entry (or lazy route) loads, with and without fragments,
against esbuild; every output run under node and compared with the unbundled source.
   usage: fragments-real.py [CASE...]   (ESB=binary, RUNS=builds per mode)"""
import gzip, json, os, re, shutil, statistics, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "out/fragments-real"
FILES = {
 "three/loader.js": "import { ObjectLoader, BufferGeometryLoader, Mesh, BoxGeometry, MeshNormalMaterial, BufferGeometry, Float32BufferAttribute, AnimationClip, VectorKeyframeTrack, AnimationMixer, Object3D } from \"three\";\nconst mesh = new Mesh(new BoxGeometry(1, 2, 3), new MeshNormalMaterial());\nmesh.name = \"box\";\nconst json = mesh.toJSON();\nconst back = new ObjectLoader().parse(json);\nconst geo = new BufferGeometryLoader().parse(new BufferGeometry().setAttribute(\"position\", new Float32BufferAttribute([0, 0, 0, 1, 0, 0, 0, 1, 0], 3)).toJSON());\nconst track = new VectorKeyframeTrack(\".position\", [0, 1], [0, 0, 0, 10, 0, 0]);\nconst clip = new AnimationClip(\"move\", 1, [track]);\nconst target = new Object3D();\nconst mixer = new AnimationMixer(target);\nmixer.clipAction(clip).play();\nmixer.update(0.5);\nconsole.log(back.name, back.geometry.type, geo.attributes.position.count, target.position.x.toFixed(2));\n",
 "three/math.js": "import { Vector3, Matrix4, Quaternion, Euler, Box3, Sphere, Plane, Ray, Color, MathUtils } from \"three\";\nconst v = new Vector3(1, 2, 3).applyMatrix4(new Matrix4().makeRotationX(Math.PI / 3));\nconst q = new Quaternion().setFromEuler(new Euler(0.1, 0.2, 0.3));\nconst b = new Box3().setFromPoints([new Vector3(0, 0, 0), new Vector3(1, 2, 3)]);\nconst r = new Ray(new Vector3(), new Vector3(0, 0, 1));\nconsole.log(v.toArray().map((x) => x.toFixed(3)).join(), q.toArray().map((x) => x.toFixed(3)).join());\nconsole.log(b.getBoundingSphere(new Sphere()).radius.toFixed(3), r.distanceToPlane(new Plane(new Vector3(0, 0, 1), -5)));\nconsole.log(new Color(0xff8040).getHexString(), MathUtils.clamp(5, 0, 1), MathUtils.lerp(0, 10, 0.25));\n",
 "three/scene.js": "import { Scene, Group, Mesh, BoxGeometry, SphereGeometry, MeshStandardMaterial, MeshBasicMaterial, PerspectiveCamera, DirectionalLight, Raycaster, Vector2 } from \"three\";\nconst scene = new Scene();\nconst group = new Group();\nfor (let i = 0; i < 5; i++) {\n  const m = new Mesh(i % 2 ? new BoxGeometry(1, 1, 1) : new SphereGeometry(0.5, 8, 6), i % 2 ? new MeshStandardMaterial({ color: 0x00ff00 }) : new MeshBasicMaterial());\n  m.position.set(i * 2, 0, -5);\n  m.name = \"m\" + i;\n  group.add(m);\n}\nscene.add(group, new DirectionalLight(0xffffff, 1));\nconst camera = new PerspectiveCamera(60, 1, 0.1, 100);\nscene.updateMatrixWorld(true);\ncamera.updateMatrixWorld(true);\nconst ray = new Raycaster();\nray.setFromCamera(new Vector2(0, 0), camera);\nconst hits = ray.intersectObjects(scene.children, true);\nlet names = [];\nscene.traverse((o) => names.push(o.type));\nconsole.log(names.join(\",\"), hits.map((h) => h.object.name + \":\" + h.distance.toFixed(3)).join());\n",
 "zod/api.js": "import { z } from \"zod\";\nconst Event = z.discriminatedUnion(\"kind\", [\n  z.object({ kind: z.literal(\"click\"), x: z.number(), y: z.number() }),\n  z.object({ kind: z.literal(\"key\"), key: z.string(), mods: z.array(z.enum([\"shift\", \"ctrl\", \"alt\"])) }),\n]);\nconst Batch = z.array(Event).max(100);\nconst r = Batch.safeParse([{ kind: \"click\", x: 1, y: 2 }, { kind: \"key\", key: \"a\", mods: [\"shift\"] }]);\nconsole.log(r.success, z.union([z.string(), z.bigint()]).safeParse(3n).success, z.record(z.string(), z.boolean()).safeParse({ a: true }).success);\n",
 "zod/forms.js": "import { z } from \"zod\";\nconst Signup = z.object({ email: z.string().email(), age: z.number().int().min(13), name: z.string().min(1).max(40) });\nconsole.log(JSON.stringify(Signup.safeParse({ email: \"a@b.co\", age: 20, name: \"x\" }).success), Signup.safeParse({ email: \"nope\", age: 2, name: \"\" }).error.issues.length);\n",
 "rx/a.js": "import { Subject, map, filter, scan } from \"rxjs\";\nconst s = new Subject(); const out = [];\ns.pipe(filter((x) => x % 2), map((x) => x * 10), scan((a, b) => a + b, 0)).subscribe((v) => out.push(v));\n[1, 2, 3, 4, 5].forEach((x) => s.next(x)); console.log(out.join());\n",
 "rx/b.js": "import { of, from, mergeMap, toArray, distinctUntilChanged, BehaviorSubject, combineLatest } from \"rxjs\";\nfrom([1, 1, 2, 3, 3]).pipe(distinctUntilChanged(), mergeMap((x) => of(x, x * 100)), toArray()).subscribe((v) => console.log(v.join()));\nconst a = new BehaviorSubject(1), b = new BehaviorSubject(2);\ncombineLatest([a, b]).subscribe(([x, y]) => console.log(x + y));\na.next(5);\n",
 "datefns/a.js": "import { format, addDays, startOfWeek } from \"date-fns\";\nconst d = new Date(2024, 0, 15);\nconsole.log(format(addDays(d, 10), \"yyyy-MM-dd\"), format(startOfWeek(d), \"EEE d MMM\"));\n",
 "datefns/b.js": "import { differenceInCalendarDays, parseISO, isWeekend, eachDayOfInterval } from \"date-fns\";\nconst a = parseISO(\"2024-03-01\"), b = parseISO(\"2024-03-20\");\nconsole.log(differenceInCalendarDays(b, a), eachDayOfInterval({ start: a, end: b }).filter(isWeekend).length);\n",
 "lodash/a.js": "import { chunk, groupBy, uniq, debounce } from \"lodash-es\";\nconsole.log(JSON.stringify(chunk([1, 2, 3, 4, 5], 2)), JSON.stringify(groupBy([1, 2, 3], (x) => x % 2)), uniq([1, 1, 2]).length, typeof debounce(() => 0, 5));\n",
 "lodash/b.js": "import { sortBy, merge, cloneDeep, template } from \"lodash-es\";\nconst o = merge({ a: { b: 1 } }, { a: { c: 2 } });\nconsole.log(JSON.stringify(sortBy([3, 1, 2])), JSON.stringify(cloneDeep(o)), template(\"hi <%= name %>\")({ name: \"x\" }));\n",
 "immer/a.js": "import { produce } from \"immer\";\nconst s = { todos: [{ done: false }, { done: false }] };\nconst n = produce(s, (d) => { d.todos[0].done = true; });\nconsole.log(n.todos[0].done, s.todos[0].done, n.todos[1] === s.todos[1]);\n",
 "immer/b.js": "import { enableMapSet, produce, createDraft, finishDraft, current, enablePatches, produceWithPatches } from \"immer\";\nenableMapSet(); enablePatches();\nconst m = produce(new Map([[\"a\", 1]]), (d) => { d.set(\"b\", 2); });\nconst draft = createDraft({ x: [1] }); draft.x.push(2); const snap = current(draft).x.length;\nconst [, patches] = produceWithPatches({ y: 1 }, (d) => { d.y = 2; });\nconsole.log(m.size, snap, finishDraft(draft).x.join(), JSON.stringify(patches));\n",
 "d3/a.js": "import { scaleLinear, scaleTime } from \"d3-scale\";\nimport { extent, bin, mean } from \"d3-array\";\nconst xs = [1, 5, 9, 2, 7];\nconst s = scaleLinear().domain(extent(xs)).range([0, 100]);\nconsole.log(s(5).toFixed(2), bin().thresholds(3)(xs).length, mean(xs), scaleTime().domain([new Date(2020, 0, 1), new Date(2021, 0, 1)]).ticks(4).length);\n",
 "d3/b.js": "import { line, curveCatmullRom, arc, pie } from \"d3-shape\";\nimport { format } from \"d3-format\";\nimport { interpolateRgb } from \"d3-interpolate\";\nconsole.log(line().curve(curveCatmullRom)([[0, 0], [1, 2], [2, 1], [3, 3]]).length, pie()([1, 2, 3]).map((p) => p.endAngle.toFixed(2)).join(), arc()({ innerRadius: 0, outerRadius: 10, startAngle: 0, endAngle: 1 }).length, format(\",.2f\")(12345.678), interpolateRgb(\"red\", \"blue\")(0.5));\n",
 "lazy/app.js": "const which = process.argv[2] || \"math\";\nconst routes = { math: () => import(\"./routeMath.js\"), scene: () => import(\"./routeScene.js\"), loader: () => import(\"./routeLoader.js\") };\nawait routes[which]();\n",
 "lazy/routeLoader.js": "import { ObjectLoader, BufferGeometryLoader, Mesh, BoxGeometry, MeshNormalMaterial, BufferGeometry, Float32BufferAttribute, AnimationClip, VectorKeyframeTrack, AnimationMixer, Object3D } from \"three\";\nconst mesh = new Mesh(new BoxGeometry(1, 2, 3), new MeshNormalMaterial());\nmesh.name = \"box\";\nconst json = mesh.toJSON();\nconst back = new ObjectLoader().parse(json);\nconst geo = new BufferGeometryLoader().parse(new BufferGeometry().setAttribute(\"position\", new Float32BufferAttribute([0, 0, 0, 1, 0, 0, 0, 1, 0], 3)).toJSON());\nconst track = new VectorKeyframeTrack(\".position\", [0, 1], [0, 0, 0, 10, 0, 0]);\nconst clip = new AnimationClip(\"move\", 1, [track]);\nconst target = new Object3D();\nconst mixer = new AnimationMixer(target);\nmixer.clipAction(clip).play();\nmixer.update(0.5);\nconsole.log(back.name, back.geometry.type, geo.attributes.position.count, target.position.x.toFixed(2));\n",
 "lazy/routeMath.js": "import { Vector3, Matrix4, Quaternion, Euler, Box3, Sphere, Plane, Ray, Color, MathUtils } from \"three\";\nconst v = new Vector3(1, 2, 3).applyMatrix4(new Matrix4().makeRotationX(Math.PI / 3));\nconst q = new Quaternion().setFromEuler(new Euler(0.1, 0.2, 0.3));\nconst b = new Box3().setFromPoints([new Vector3(0, 0, 0), new Vector3(1, 2, 3)]);\nconst r = new Ray(new Vector3(), new Vector3(0, 0, 1));\nconsole.log(v.toArray().map((x) => x.toFixed(3)).join(), q.toArray().map((x) => x.toFixed(3)).join());\nconsole.log(b.getBoundingSphere(new Sphere()).radius.toFixed(3), r.distanceToPlane(new Plane(new Vector3(0, 0, 1), -5)));\nconsole.log(new Color(0xff8040).getHexString(), MathUtils.clamp(5, 0, 1), MathUtils.lerp(0, 10, 0.25));\n",
 "lazy/routeScene.js": "import { Scene, Group, Mesh, BoxGeometry, SphereGeometry, MeshStandardMaterial, MeshBasicMaterial, PerspectiveCamera, DirectionalLight, Raycaster, Vector2 } from \"three\";\nconst scene = new Scene();\nconst group = new Group();\nfor (let i = 0; i < 5; i++) {\n  const m = new Mesh(i % 2 ? new BoxGeometry(1, 1, 1) : new SphereGeometry(0.5, 8, 6), i % 2 ? new MeshStandardMaterial({ color: 0x00ff00 }) : new MeshBasicMaterial());\n  m.position.set(i * 2, 0, -5);\n  m.name = \"m\" + i;\n  group.add(m);\n}\nscene.add(group, new DirectionalLight(0xffffff, 1));\nconst camera = new PerspectiveCamera(60, 1, 0.1, 100);\nscene.updateMatrixWorld(true);\ncamera.updateMatrixWorld(true);\nconst ray = new Raycaster();\nray.setFromCamera(new Vector2(0, 0), camera);\nconst hits = ray.intersectObjects(scene.children, true);\nlet names = [];\nscene.traverse((o) => names.push(o.type));\nconsole.log(names.join(\",\"), hits.map((h) => h.object.name + \":\" + h.distance.toFixed(3)).join());\n"
}
HERE.mkdir(parents=True, exist_ok=True)
for name, text in FILES.items():
    (HERE / name).parent.mkdir(parents=True, exist_ok=True)
    (HERE / name).write_text(text)
(HERE / "package.json").write_text('{"type":"module"}')
if not (HERE / "node_modules").exists():
    (HERE / "node_modules").symlink_to(ROOT / "tests/node_modules")
ESB = Path(os.environ.get("ESB", ROOT / "out/bin/esb")).resolve()
ESBUILD = ROOT / "tests/node_modules/.bin/esbuild"
RUNS = int(os.environ.get("RUNS", "5"))

CASES = {
    "three": ["three/math.js", "three/scene.js", "three/loader.js"],
    "zod": ["zod/forms.js", "zod/api.js"],
    "rxjs": ["rx/a.js", "rx/b.js"],
    "date-fns": ["datefns/a.js", "datefns/b.js"],
    "lodash-es": ["lodash/a.js", "lodash/b.js"],
    "immer": ["immer/a.js", "immer/b.js"],
    "d3": ["d3/a.js", "d3/b.js"],
    "three-lazy": ["lazy/app.js"],
}
ROUTES = {"three-lazy": ["math", "scene", "loader"]}

STATIC = re.compile(r'(?:^|[;}\n])\s*(?:import|export)\s*(?:[\w$*{},\s]*?\bfrom\s*)?"(\./[^"]+)"')
DYNAMIC = re.compile(r'import\(\s*"(\./[^"]+)"\s*\)')


def closure(outdir, start):
    seen, todo = set(), [start]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        text = (outdir / f).read_text()
        for m in STATIC.finditer(text):
            todo.append(os.path.normpath(os.path.join(os.path.dirname(f), m.group(1))))
    return seen


def size(outdir, files):
    raw = sum((outdir / f).stat().st_size for f in files)
    gz = sum(len(gzip.compress((outdir / f).read_bytes(), 9)) for f in files)
    return raw, gz


def build(tool, entries, outdir, extra):
    if outdir.exists():
        shutil.rmtree(outdir)
    if tool == "esbuild":
        cmd = [str(ESBUILD), *entries, "--bundle", "--splitting", "--format=esm", "--platform=node",
               f"--outdir={outdir}", "--log-level=error", *extra]
    else:
        cmd = [str(ESB), *entries, "--splitting", "--format=esm", "--platform=node", f"--outdir={outdir}", *extra]
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    dt = time.perf_counter() - t
    if p.returncode != 0:
        raise SystemExit(f"{' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
    return dt


def oracle(entry, arg=None):
    return subprocess.run(["node", entry] + ([arg] if arg else []), cwd=HERE, capture_output=True, text=True).stdout


MODES = [
    ("esbuild", "esbuild", []),
    ("ours-modules", "esb", []),
    ("ours-fragments", "esb", ["--fragments"]),
    ("esbuild-min", "esbuild", ["--minify"]),
    ("ours-modules-min", "esb", ["--minify"]),
    ("ours-fragments-min", "esb", ["--minify", "--fragments"]),
]

results = []
only = sys.argv[1:]
for case, entries in CASES.items():
    if only and case not in only:
        continue
    for mode, tool, extra in MODES:
        outdir = HERE / "out" / case / mode
        times = [build(tool, entries, outdir, extra) for _ in range(RUNS if tool != "esbuild" else 3)]
        files = sorted(str(p.relative_to(outdir)) for p in outdir.rglob("*.js"))
        total_raw, total_gz = size(outdir, files)
        loads = {}
        ok = True
        if case in ROUTES:
            app = "app.js"
            app_set = closure(outdir, app)
            text = "".join((outdir / f).read_text() for f in app_set)
            dyn = [os.path.normpath(m.group(1)) for m in DYNAMIC.finditer(text)]
            for r in ROUTES[case]:
                target = next(d for d in dyn if Path(d).name.lower().startswith("route" + r))
                loads[r] = size(outdir, app_set | closure(outdir, target))
                got = subprocess.run(["node", str(outdir / app), r], capture_output=True, text=True)
                want = oracle(entries[0], r)
                if got.stdout != want or got.returncode:
                    ok = False
                    print(f"  MISMATCH {case}/{mode}/{r}: {got.stdout!r} {got.stderr[-400:]!r} want {want!r}")
        else:
            for e in entries:
                out = Path(e).name
                loads[Path(e).stem] = size(outdir, closure(outdir, out))
                got = subprocess.run(["node", str(outdir / out)], capture_output=True, text=True)
                want = oracle(e)
                if got.stdout != want or got.returncode:
                    ok = False
                    print(f"  MISMATCH {case}/{mode}/{e}: {got.stdout!r} {got.stderr[-400:]!r} want {want!r}")
        row = dict(case=case, mode=mode, files=len(files), total_raw=total_raw, total_gz=total_gz,
                   loads=loads, ms=round(statistics.median(times) * 1000, 1), same_as_node=ok)
        results.append(row)
        print(json.dumps(row), flush=True)

(HERE / "results.json").write_text(json.dumps(results, indent=1))
