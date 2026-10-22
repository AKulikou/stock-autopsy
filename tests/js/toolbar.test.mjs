// The report toolbar looks and behaves like tabs and stays on one row on a desktop:
// checked on the stylesheet the page loads, since the page tests run without a browser.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const css = readFileSync(new URL("../../web/static/app.css", import.meta.url), "utf8");

function rule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = css.match(new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`));
  assert.ok(match, `no rule for ${selector}`);
  return match[1];
}

test("the selected tab is marked by an underline and does not look clickable", () => {
  const selected = rule('.tab[aria-selected="true"]');
  assert.match(selected, /border-bottom-color:\s*var\(--accent\)/);
  assert.match(selected, /cursor:\s*default/);
  assert.doesNotMatch(selected, /background:\s*var\(--accent\)/); // not a filled button any more
  const hover = rule('.tab:not([aria-selected="true"]):hover');
  assert.match(hover, /border-bottom-color/);
});

test("on a desktop the toolbar is one row: tabs left, actions right, spaced by tokens", () => {
  assert.match(rule(".toolbar-row"), /flex-wrap:\s*nowrap/);
  assert.match(rule(".toolbar-row"), /gap:\s*var\(--space-\d\)/);
  assert.match(rule(".toolbar-actions"), /margin-left:\s*auto/);
  assert.match(rule(".toolbar-actions"), /gap:\s*var\(--space-\d\)/);
  // Only a narrow screen may wrap, and it keeps the spacing.
  const narrow = css.slice(css.indexOf("@media (max-width: 760px)"));
  assert.ok(narrow.length > 0 && /\.toolbar-row\s*\{[^}]*flex-wrap:\s*wrap/.test(narrow));
});
