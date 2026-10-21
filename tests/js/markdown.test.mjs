// The Markdown renderer of the translated report (web/static/markdown.js).
import assert from "node:assert/strict";
import { test } from "node:test";

import { renderMarkdown } from "../../web/static/markdown.js";

test("the report's collapsible claims render as a details block, not as visible tags", () => {
  const html = renderMarkdown("<details><summary>Утверждения</summary>\n\n- one claim\n\n</details>");
  assert.equal(html, "<details><summary>Утверждения</summary>\n<ul><li>one claim</li></ul>\n</details>");
});

test("the summary text is escaped like any other text", () => {
  const html = renderMarkdown('<details><summary><img src=x onerror="alert(1)"></summary>\n\n</details>');
  assert.ok(!html.includes("<img"));
  assert.ok(html.startsWith("<details><summary>&lt;img"));
});

test("other raw HTML stays text, and a stray closing tag is not markup", () => {
  assert.equal(renderMarkdown("<b>bold</b>"), "<p>&lt;b&gt;bold&lt;/b&gt;</p>");
  assert.equal(renderMarkdown("</details>"), "<p>&lt;/details&gt;</p>");
});

test("a details block the translation left open is closed at the end", () => {
  const html = renderMarkdown("<details><summary>Claims</summary>\n\ntext");
  assert.ok(html.endsWith("</details>"));
});
