// The glossary and the cost table are closed blocks on the page (web/static/collapsed.js).
import assert from "node:assert/strict";
import { test } from "node:test";

import { costMarkdown, glossaryMarkdown } from "../../web/static/collapsed.js";
import { renderMarkdown } from "../../web/static/markdown.js";

const glossary = { title: "Glossary", entries: [
  { term: "free cash flow (FCF)", explanation: "Operating cash flow minus capital expenditure." },
  { term: "done / failed", explanation: "Whether a call to the model ended with a usable answer." },
] };

test("the glossary renders as a closed details block with one item per term", () => {
  const html = renderMarkdown(glossaryMarkdown(glossary));
  assert.ok(html.startsWith("<details><summary>Glossary</summary>"));
  assert.ok(!html.includes("<details open"));
  assert.ok(html.includes("<li><strong>free cash flow (FCF)</strong>: Operating cash flow minus capital expenditure.</li>"));
  assert.ok(html.trimEnd().endsWith("</details>"));
  assert.equal(glossaryMarkdown({ title: "Glossary", entries: [] }), "");
});

test("the cost table renders as a closed details block named Cost", () => {
  const cost = { columns: ["Call", "Status", "Input"], rows: [["Forensic Accountant", "done", "651"]] };
  const html = renderMarkdown(costMarkdown(cost, "Total: $0.58, 148 s."));
  assert.ok(html.startsWith("<details><summary>Cost</summary>"));
  assert.ok(html.includes("<td>Forensic Accountant</td>") && html.includes("Total: $0.58, 148 s."));
  assert.ok(!html.includes("<details open"));
});

test("a translation's glossary and collapsed cost section render closed under their own titles", () => {
  const markdown = "## Итог\n\nтекст\n\n<details><summary>Стоимость</summary>\n\n| Вызов | Статус |\n|---|---|\n"
    + "| A | выполнено |\n\n</details>\n\n<details><summary>Словарь</summary>\n\n- **выручка** (revenue): Деньги.\n\n</details>\n";
  const html = renderMarkdown(markdown);
  assert.ok(html.includes("<details><summary>Стоимость</summary>"));
  assert.ok(html.includes("<details><summary>Словарь</summary>"));
  assert.ok(!html.includes("<details open"));
});
