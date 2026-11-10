// A boundary reference can be put into an application's model, but never called on the server.
// The paired browser bundle resolves its module/export pair. This is not the Flight protocol.
export function clientReference(moduleId, exportName) {
  const reference = function () {
    throw new Error("Cannot call client export " + exportName + " from " + moduleId + " on the server");
  };
  return Object.freeze(Object.defineProperties(reference, {
    $$typeof: { value: Symbol.for("react.client.reference") },
    $$id: { value: JSON.stringify([moduleId, exportName]) },
    $$async: { value: false },
    moduleId: { value: moduleId },
    exportName: { value: exportName },
    toJSON: { value: () => ({ module: moduleId, export: exportName }) }
  }));
}
