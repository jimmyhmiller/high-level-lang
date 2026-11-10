// The browser owns the implementations. Validate references before returning an export.
export function resolveClientReference(reference) {
  if (!reference || typeof reference.module !== "string" || typeof reference.export !== "string" ||
      !Object.prototype.hasOwnProperty.call(modules, reference.module)) {
    throw new Error("Unknown client module reference");
  }
  const namespace = modules[reference.module];
  if (!Object.prototype.hasOwnProperty.call(namespace, reference.export)) {
    throw new Error("Unknown client export " + reference.export + " from " + reference.module);
  }
  return namespace[reference.export];
}
