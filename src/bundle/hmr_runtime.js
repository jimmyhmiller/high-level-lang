// The development runtime: modules by id, each run once and its exports kept on one namespace
// object, which hot updates refill in place, so what imported it reads the new values. A module's
// function first hands over an evaluator of its own scope; a patch is code run there, giving the
// names of the statements that changed their new values while the module keeps its state.
var __hmr = (() => {
  var defined = Object.create(null);
  var running = Object.create(null);
  var spaces = Object.create(null);
  var datas = Object.create(null);
  var entry = null;
  var display = (id) => id.startsWith(base) ? id.slice(base.length) : id;
  var base = typeof __hmr_base === "string" ? __hmr_base : "";
  var log = (text) => typeof console !== "undefined" && console.log("[hmr] " + text);

  // A module's namespace: the same object every time it runs. Its own exports are getters on it;
  // what `export *` brings is looked up in the modules it names when it is read, as an ES module's
  // is, so a module still running in a cycle cannot leave names out.
  var stars = Object.create(null);
  var space = (id) => spaces[id] || (spaces[id] = namespace(id));
  var starred = (id, key) => {
    if (key === "default" || typeof key !== "string") return undefined;
    for (var ns of stars[id] || []) if (key in ns) return ns;
    return undefined;
  };
  var namespace = (id) => {
    var own = Object.create(null, { [Symbol.toStringTag]: { value: "Module", configurable: true } });
    return new Proxy(own, {
      get: (t, key) => key in t ? t[key] : (starred(id, key) || {})[key],
      has: (t, key) => key in t || starred(id, key) !== undefined,
      ownKeys: (t) => {
        var keys = Reflect.ownKeys(t);
        for (var ns of stars[id] || []) for (var key of Object.keys(ns)) if (key !== "default" && !keys.includes(key)) keys.push(key);
        return keys;
      },
      getOwnPropertyDescriptor: (t, key) => {
        if (Object.prototype.hasOwnProperty.call(t, key)) return Reflect.getOwnPropertyDescriptor(t, key);
        var ns = starred(id, key);
        return ns && { value: ns[key], enumerable: true, configurable: true, writable: false };
      },
      defineProperty: (t, key, desc) => Reflect.defineProperty(t, key, desc),
      deleteProperty: (t, key) => Reflect.deleteProperty(t, key)
    });
  };

  var define = (id, deps, factory, esm) => {
    defined[id] = { deps, factory, esm };
  };

  // What a module's code is given: its namespace's getters, imports, require, and import.meta.
  var context = (id, rec) => {
    var deps = defined[id].deps;
    var target = (kind, spec) => {
      spec = kind + ":" + spec;
      if (!(spec in deps)) throw new Error("[hmr] " + id + " imports " + spec + ", which the build did not resolve");
      return deps[spec];
    };
    var outside = (spec) => {
      if (typeof require === "function") return require(spec);
      throw new Error("[hmr] " + spec + " is outside the bundle, and nothing here can load it");
    };
    return {
      export(getters) {
        for (var name in getters) Object.defineProperty(rec.ns, name, { get: getters[name], enumerable: true, configurable: true });
      },
      // A patch's exports: these, and no others of the module's own.
      exportOnly(getters) {
        for (var name of Reflect.ownKeys(rec.ns)) if (name !== Symbol.toStringTag && !(name in getters)) delete rec.ns[name];
        this.export(getters);
      },
      scope(evaluate) { rec.scope = evaluate; },
      // A class's methods, from a class of them alone, put on the class there is, so the instances
      // it made have them; and methods taken out (`#m` on the prototype, `.m` on the class) deleted.
      patchClass(target, fresh) {
        for (var key of Reflect.ownKeys(fresh.prototype)) if (key !== "constructor") Object.defineProperty(target.prototype, key, Reflect.getOwnPropertyDescriptor(fresh.prototype, key));
        for (var key of Reflect.ownKeys(fresh)) if (key !== "prototype" && key !== "length" && key !== "name") Object.defineProperty(target, key, Reflect.getOwnPropertyDescriptor(fresh, key));
      },
      unpatchClass(target, keys) {
        for (var key of keys) delete (key[0] === "#" ? target.prototype : target)[key.slice(1)];
      },
      // What a class extends, for a class of its methods to extend too.
      parentOf(c) {
        var parent = Object.getPrototypeOf(c);
        return parent === Function.prototype ? null : parent;
      },
      star(ns) {
        (stars[id] || (stars[id] = [])).push(ns);
      },
      import(spec) {
        var t = target("import", spec);
        if (t === null) return __toESM(outside(spec));
        var r = load(t);
        return r.esm ? r.ns : __toESM(r.module.exports);
      },
      // A module imported `with { type: "json" }`: its JSON module, keyed apart.
      importJson(spec) {
        var t = target("json", spec);
        if (t === null) throw new Error("[hmr] " + spec + " is a JSON module outside the bundle, and nothing here can load it");
        return load(t).ns;
      },
      require(spec) {
        var t = target("require", spec);
        if (t === null) return outside(spec);
        var r = load(t);
        return r.esm ? __toCommonJS(r.ns) : r.module.exports;
      },
      meta: { url: id, hot: rec.hot }
    };
  };

  // `import.meta.hot`, as Vite has it: `data` is the module's one object for as long as the page
  // lives, given to each run and to the disposers; each `accept(callback)` is kept, and when the
  // module runs again the last run's are called with its new exports (and, after them, the exports
  // the last run had).
  var hotFor = (id, rec) => ({
    data: datas[id] || (datas[id] = {}),
    accept(callback) { rec.accepted.push(callback || null); },
    dispose(callback) { rec.disposers.push(callback); },
    invalidate(why) { reload(display(id) + (why ? ": " + why : " asked to be reloaded")); }
  });

  // A module, run the first time it is asked for. One being run is answered as it is so far, as a
  // cycle of ES modules is.
  var load = (id) => {
    if (running[id]) return running[id];
    var def = defined[id];
    if (!def) throw new Error("[hmr] no module " + id);
    var rec = running[id] = { id, esm: def.esm, ns: space(id), module: null, accepted: [], disposers: [], scope: null };
    rec.hot = hotFor(id, rec);
    for (var name of Reflect.ownKeys(rec.ns)) if (name !== Symbol.toStringTag) delete rec.ns[name];
    stars[id] = [];
    var ctx = context(id, rec);
    if (def.esm) {
      rec.module = { exports: rec.ns };
      def.factory.call(undefined, ctx);
    } else {
      rec.module = { exports: {} };
      def.factory.call(rec.module.exports, rec.module, rec.module.exports, ctx.require, ctx);
    }
    return rec;
  };

  var start = (id) => {
    entry = id;
    load(id);
  };

  var reload = (why) => {
    log("reload: " + why);
    if (typeof location !== "undefined") location.reload();
    else if (typeof __hmr_reloaded === "function") __hmr_reloaded(why);
  };

  // New code for `changed`; `patches`, code run in the scopes of modules that keep running; `stale`
  // modules to run again, which the build found between what changed and the modules that accept
  // it, `boundaries`. Each stale module's disposers run first, and what they put in `hot.data` goes
  // to the module's next run. `notes` say what was patched, and why what runs again does.
  var update = (changed, stale, boundaries, patches, notes) => {
    for (var id in changed) define(id, ...changed[id]);
    for (var note of notes) log(note);
    for (var id in patches) {
      var rec = running[id];
      if (!rec || !rec.scope) continue;
      try {
        rec.scope = rec.scope(patches[id]);
      } catch (e) {
        reload("patching " + display(id) + " failed: " + (e && e.message));
        return;
      }
    }
    var last = Object.create(null);
    for (var id of stale) {
      var rec = running[id];
      if (!rec) continue;
      var data = datas[id] || (datas[id] = {});
      for (var dispose of rec.disposers) dispose(data);
      var exports = {};
      for (var key of Reflect.ownKeys(rec.ns)) if (typeof key === "string") exports[key] = rec.ns[key];
      last[id] = { accepted: rec.accepted, exports };
      delete running[id];
    }
    for (var id of boundaries) {
      var rec = load(id);
      var before = last[id];
      for (var accepted of before ? before.accepted : rec.accepted) if (accepted) accepted(rec.ns, before && before.exports);
    }
    if (boundaries.length > 0) log("updated " + boundaries.map(display).join(", "));
  };

  // Each update is a script, run by `apply`, which the bundle gives from its own top level: where
  // the first build's modules were defined, seeing the same names they did.
  var connect = (url, apply) => {
    if (typeof EventSource !== "undefined") {
      var source = new EventSource(url);
      source.addEventListener("update", (e) => apply(e.data));
      source.addEventListener("reload", (e) => reload(e.data));
      return;
    }
    if (typeof require !== "function") return;
    require("http").get(url, (res) => {
      var buffer = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        buffer += chunk;
        var cut;
        while ((cut = buffer.indexOf("\n\n")) >= 0) {
          var block = buffer.slice(0, cut);
          buffer = buffer.slice(cut + 2);
          var event = "message", data = [];
          for (var line of block.split("\n")) {
            if (line.startsWith("event: ")) event = line.slice(7);
            else if (line.startsWith("data: ")) data.push(line.slice(6));
          }
          if (event === "update") apply(data.join("\n"));
          else if (event === "reload") reload(data.join("\n"));
        }
      });
    });
  };

  return { define, start, update, connect, reload };
})();
