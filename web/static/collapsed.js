// Blocks the English view shows collapsed (D5), written as the Markdown report.md uses, so the
// page renders them like the translation tab does: closed <details>, text escaped by markdown.js.

function cell(text) {
  return String(text).replace(/\|/g, "\\|");
}

// The glossary of the terms the report uses: "<details><summary>Glossary</summary>" and a list.
export function glossaryMarkdown(glossary) {
  if (!glossary || !glossary.entries.length) return "";
  const items = glossary.entries.map((e) => `- **${e.term}**: ${e.explanation}`);
  return `<details><summary>${glossary.title}</summary>\n\n${items.join("\n")}\n\n</details>`;
}

// The cost table of report.md, one row per call, closed until asked for.
export function costMarkdown(cost, totalText) {
  if (!cost || !cost.rows.length) return "";
  const lines = [
    `| ${cost.columns.map(cell).join(" | ")} |`,
    `|${cost.columns.map(() => "---").join("|")}|`,
    ...cost.rows.map((row) => `| ${row.map(cell).join(" | ")} |`),
  ];
  return `<details><summary>Cost</summary>\n\n${lines.join("\n")}\n\n${totalText}\n\n</details>`;
}
