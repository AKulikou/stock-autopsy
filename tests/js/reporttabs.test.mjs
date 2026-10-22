// The report tabs (web/static/reporttabs.js).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  ORIGINAL,
  languageOptions,
  needsTranslation,
  saveTarget,
  tabKeyTarget,
  tabLabel,
} from "../../web/static/reporttabs.js";

const translations = new Map([
  ["Lithuanian", { code: "lt", label: "Lietuvių", download_label: "Save report in Lithuanian (.md)" }],
  ["Russian", { code: "ru", label: "Русский", download_label: "Save report in Russian (.md)" }],
]);

test("arrow keys move between tabs and wrap; Home and End jump to the ends", () => {
  assert.equal(tabKeyTarget("ArrowRight", 0, 3), 1);
  assert.equal(tabKeyTarget("ArrowRight", 2, 3), 0);
  assert.equal(tabKeyTarget("ArrowLeft", 0, 3), 2);
  assert.equal(tabKeyTarget("Home", 2, 3), 0);
  assert.equal(tabKeyTarget("End", 0, 3), 2);
  assert.equal(tabKeyTarget("Enter", 0, 3), null);
  assert.equal(tabKeyTarget("ArrowRight", 0, 0), null);
});

test("Save saves the copy in the open tab, with its own file name", () => {
  assert.deepEqual(saveTarget("r1", ORIGINAL, translations),
    { href: "/api/runs/r1/files/report", label: "Save report (.md)" });
  assert.deepEqual(saveTarget("r1", "Lithuanian", translations),
    { href: "/api/runs/r1/translations/lt", label: "Save report in Lithuanian (.md)" });
});

test("tabs are named English and by each language's own name", () => {
  assert.equal(tabLabel(ORIGINAL, translations), "English");
  assert.equal(tabLabel("Russian", translations), "Русский");
});

test("a language translated in this session is not translated again", () => {
  assert.equal(needsTranslation("Lithuanian", translations), false);
  assert.equal(needsTranslation("German", translations), true);
});

// As /api/options sends them: Startup Autopsy's list and order.
const OFFERED = [
  ["Lithuanian", "Lietuvių"], ["German", "Deutsch"], ["Estonian", "Eesti"], ["Spanish", "Español"],
  ["French", "Français"], ["Italian", "Italiano"], ["Latvian", "Latviešu"], ["Polish", "Polski"],
  ["Russian", "Русский"], ["Ukrainian", "Українська"],
].map(([name, label]) => ({ name, label }));

test("the language select keeps the server's order and opens on Lietuvių", () => {
  const options = languageOptions(OFFERED, "Lithuanian");
  assert.deepEqual(options.map((o) => o.label), [
    "Lietuvių", "Deutsch", "Eesti", "Español", "Français", "Italiano", "Latviešu", "Polski", "Русский", "Українська",
  ]);
  assert.deepEqual(options.filter((o) => o.selected).map((o) => o.value), ["Lithuanian"]);
});

test("a language remembered by the old page does not change the selection on load", () => {
  // The page of 2026-10-22 stored the last choice; a browser may still hold it.
  const stored = new Map([["stock-autopsy.translation-language", "Russian"]]);
  globalThis.localStorage = { getItem: (key) => stored.get(key) ?? null, setItem: (k, v) => stored.set(k, v) };
  try {
    const selected = languageOptions(OFFERED, "Lithuanian").filter((o) => o.selected);
    assert.deepEqual(selected.map((o) => o.label), ["Lietuvių"]);
  } finally {
    delete globalThis.localStorage;
  }
  // Nothing on the page reads or writes the stored choice any more.
  for (const file of ["app.js", "reporttabs.js"]) {
    const source = readFileSync(new URL(`../../web/static/${file}`, import.meta.url), "utf8");
    assert.doesNotMatch(source, /localStorage|translation-language|prefs\.js/, file);
  }
});
