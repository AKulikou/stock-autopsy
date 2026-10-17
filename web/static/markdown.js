// A small Markdown renderer for the lens analyses and the translated report:
// headings, paragraphs, bullet and numbered lists, tables, horizontal rules,
// quotes, bold, italic, inline code and links. Raw HTML is never rendered.
// Every piece of text is HTML-escaped before any markup is added, so model
// output can never inject HTML into the page.
//
// Links: a web address (http or https) opens in a new tab; any other target is a
// file next to the report on disk (for example lenses/reality_auditor.md), which
// means nothing on this page, so only the link text is shown.

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function inline(text) {
  // Code spans and link targets are set aside first, so emphasis rules never
  // touch them (an address like a_b_c must not turn into italics).
  const kept = [];
  const keep = (html) => {
    kept.push(html);
    return `\u0000${kept.length - 1}\u0000`;
  };
  let html = escapeHtml(text).replace(/`([^`]+)`/g, (_, code) => keep(`<code>${code}</code>`));
  html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, target) =>
    /^https?:\/\//i.test(target)
      ? `${keep(`<a href="${target}" target="_blank" rel="noopener noreferrer">`)}${label}${keep("</a>")}`
      : label,
  );
  html = html
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^\w*])\*(?!\s)([^*\n]+?)\*(?![\w*])/g, "$1<em>$2</em>")
    .replace(/(^|[^\w])_(?!\s)([^_\n]+?)_(?!\w)/g, "$1<em>$2</em>");
  return html.replace(/\u0000(\d+)\u0000/g, (_, i) => kept[Number(i)]);
}

const PATTERNS = {
  heading: /^(#{1,6})\s+(.*)$/,
  rule: /^\s*([-*_])(\s*\1){2,}\s*$/,
  bullet: /^(\s*)[-*+]\s+(.*)$/,
  numbered: /^(\s*)\d+[.)]\s+(.*)$/,
  quote: /^>\s?(.*)$/,
  tableRow: /^\s*\|.*\|\s*$/,
  // Extra trailing pipes ("|---|---||") occur in model output; accept them.
  tableDivider: /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|*\s*$/,
};

function cells(row) {
  return row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

function renderTable(rows) {
  const [head, , ...body] = rows;
  const th = cells(head).map((c) => `<th>${inline(c)}</th>`).join("");
  const trs = body
    .map((row) => `<tr>${cells(row).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`)
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table></div>`;
}

// Lists: items indented under an item become a nested list.
function renderList(lines, start) {
  const first = lines[start].match(PATTERNS.bullet) || lines[start].match(PATTERNS.numbered);
  const indent = first[1].length;
  const ordered = PATTERNS.numbered.test(lines[start]) && !PATTERNS.bullet.test(lines[start]);
  const tag = ordered ? "ol" : "ul";
  let html = `<${tag}>`;
  let i = start;
  let open = false;
  while (i < lines.length) {
    const line = lines[i];
    const item = line.match(PATTERNS.bullet) || line.match(PATTERNS.numbered);
    if (item && item[1].length === indent) {
      if (open) html += "</li>";
      html += `<li>${inline(item[2])}`;
      open = true;
      i += 1;
    } else if (item && item[1].length > indent) {
      const [nested, next] = renderList(lines, i);
      html += nested;
      i = next;
    } else if (line.trim() && /^\s{2,}\S/.test(line) && open) {
      html += ` ${inline(line.trim())}`; // continuation of the item's text
      i += 1;
    } else {
      break;
    }
  }
  if (open) html += "</li>";
  return [`${html}</${tag}>`, i];
}

export function renderMarkdown(markdown) {
  const lines = (markdown || "").replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let paragraph = [];
  const flush = () => {
    if (paragraph.length) out.push(`<p>${paragraph.map(inline).join("<br>")}</p>`);
    paragraph = [];
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      flush();
      i += 1;
    } else if (PATTERNS.heading.test(line)) {
      flush();
      const [, hashes, text] = line.match(PATTERNS.heading);
      const level = Math.min(hashes.length + 2, 6); // the page already has h1/h2
      out.push(`<h${level}>${inline(text)}</h${level}>`);
      i += 1;
    } else if (PATTERNS.rule.test(line)) {
      flush();
      out.push("<hr>");
      i += 1;
    } else if (PATTERNS.tableRow.test(line) && PATTERNS.tableDivider.test(lines[i + 1] || "")) {
      flush();
      const rows = [];
      while (i < lines.length && PATTERNS.tableRow.test(lines[i])) rows.push(lines[i++]);
      out.push(renderTable(rows));
    } else if (PATTERNS.bullet.test(line) || PATTERNS.numbered.test(line)) {
      flush();
      const [html, next] = renderList(lines, i);
      out.push(html);
      i = next;
    } else if (PATTERNS.quote.test(line)) {
      flush();
      const quoted = [];
      while (i < lines.length && PATTERNS.quote.test(lines[i])) {
        quoted.push(lines[i].match(PATTERNS.quote)[1]);
        i += 1;
      }
      out.push(`<blockquote>${quoted.map(inline).join("<br>")}</blockquote>`);
    } else {
      paragraph.push(line.trim());
      i += 1;
    }
  }
  flush();
  return out.join("\n");
}
