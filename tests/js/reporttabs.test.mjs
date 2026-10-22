// The report tabs (web/static/reporttabs.js).
import assert from "node:assert/strict";
import { test } from "node:test";

import { ORIGINAL, needsTranslation, saveTarget, tabKeyTarget, tabLabel } from "../../web/static/reporttabs.js";

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
