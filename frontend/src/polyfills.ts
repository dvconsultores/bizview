/**
 * Safari/iOS 14 (research R8) lacks ES2022 built-ins that bundled libraries call:
 * `Object.hasOwn` (react-markdown) and `Array#at` (react-resizable-panels). Imported first by
 * main.tsx; scripts/check-compat.mjs skips these two rules only while that import exists.
 */
function define(target: object, name: string, value: unknown) {
  if (!(name in target)) {
    Object.defineProperty(target, name, { value, configurable: true, writable: true });
  }
}

define(Object, "hasOwn", (object: object, key: PropertyKey) =>
  Object.prototype.hasOwnProperty.call(object, key));

function at(this: ArrayLike<unknown>, index: number) {
  let i = Math.trunc(index) || 0;
  if (i < 0) i += this.length;
  return i < 0 || i >= this.length ? undefined : this[i];
}
define(Array.prototype, "at", at);
define(String.prototype, "at", at);
