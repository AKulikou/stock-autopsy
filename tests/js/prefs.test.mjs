// The remembered translation language (web/static/prefs.js, D3).
import assert from "node:assert/strict";
import { test } from "node:test";

import { rememberLanguage, rememberedLanguage } from "../../web/static/prefs.js";

const OFFERED = [{ name: "Lithuanian" }, { name: "Russian" }, { name: "German" }];

function memoryStorage() {
  const items = new Map();
  return { getItem: (k) => (items.has(k) ? items.get(k) : null), setItem: (k, v) => items.set(k, String(v)) };
}

const broken = {
  getItem() { throw new Error("SecurityError"); },
  setItem() { throw new Error("QuotaExceededError"); },
};

test("without a remembered choice the server's default is used", () => {
  assert.equal(rememberedLanguage(memoryStorage(), OFFERED, "Lithuanian"), "Lithuanian");
});

test("the last chosen language is remembered", () => {
  const storage = memoryStorage();
  rememberLanguage(storage, "Russian");
  assert.equal(rememberedLanguage(storage, OFFERED, "Lithuanian"), "Russian");
});

test("a remembered language that is no longer offered falls back to the default", () => {
  const storage = memoryStorage();
  rememberLanguage(storage, "Klingon");
  assert.equal(rememberedLanguage(storage, OFFERED, "Lithuanian"), "Lithuanian");
});

test("missing or failing storage never breaks the page", () => {
  assert.equal(rememberedLanguage(null, OFFERED, "Lithuanian"), "Lithuanian");
  assert.equal(rememberedLanguage(broken, OFFERED, "Lithuanian"), "Lithuanian");
  assert.doesNotThrow(() => rememberLanguage(broken, "Russian"));
  assert.doesNotThrow(() => rememberLanguage(null, "Russian"));
});
