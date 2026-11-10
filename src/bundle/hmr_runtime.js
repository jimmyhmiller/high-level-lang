// The development runtime: modules by id, each run once and its exports kept on one namespace
// object, which hot updates refill in place, so what imported it reads the new values.
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
      star(ns) {
        (stars[id] || (stars[id] = [])).push(ns);
      },
      import(spec) {
        var t = target("import", spec);
        if (t === null) return __toESM(outside(spec));
        var r = load(t);
        return r.esm ? r.ns : __toESM(r.module.exports);
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

  var hotFor = (id, rec) => ({
    data: datas[id] || {},
    accept(callback) { rec.accepted = callback || (() => {}); },
    dispose(callback) { rec.disposers.push(callback); },
    invalidate() { reload(id + " asked to be reloaded"); }
  });

  // A module, run the first time it is asked for. One being run is answered as it is so far, as a
  // cycle of ES modules is.
  var load = (id) => {
    if (running[id]) return running[id];
    var def = defined[id];
    if (!def) throw new Error("[hmr] no module " + id);
    var rec = running[id] = { id, esm: def.esm, ns: space(id), module: null, accepted: null, disposers: [] };
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

  // New code for `changed`; `stale` modules to run again, which the build found between what
  // changed and the modules that accept it, `boundaries`. Each stale module's disposers run first,
  // and what they put in `hot.data` goes to the module's next run.
  var update = (changed, stale, boundaries) => {
    for (var id in changed) define(id, ...changed[id]);
    for (var id of stale) {
      var rec = running[id];
      if (!rec) continue;
      var data = {};
      for (var dispose of rec.disposers) dispose(data);
      datas[id] = data;
      delete running[id];
    }
    for (var id of boundaries) {
      var rec = load(id);
      if (rec.accepted) rec.accepted(rec.ns);
    }
    log("updated " + boundaries.map(display).join(", "));
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
