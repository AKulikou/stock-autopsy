// What the company lookup shows (decision D5): a card per candidate and the notice above them.
// Colour is never the only signal: every card has an icon and a text label.

const ORDER = { exact: 0, related: 1, unavailable: 2 };

// "Files Form 20-F (a foreign company): this version reads ..." -> "Files Form 20-F".
export function shortReason(reason) {
  return reason.split(/ \(|:/)[0].trim();
}

// The look of one candidate: kind (exact / related / unavailable), icon, label, and whether it can run.
export function candidateCard(c) {
  const related = c.match_type === "related";
  const icon = related ? "↔" : "✓";
  let label = related ? `Related: ${c.relation || "a related company"}` : "Exact match";
  if (c.share_class) label += ` · ${c.share_class}`;
  if (c.unsupported) {
    return { kind: "unavailable", icon, label: `${label} · ${shortReason(c.unsupported)}`, canRun: false };
  }
  return { kind: related ? "related" : "exact", icon, label, canRun: true };
}

// Exact matches first, then related companies, then those that cannot be analyzed.
export function orderCandidates(candidates) {
  return candidates
    .map((c, index) => ({ c, index, rank: ORDER[candidateCard(c).kind] }))
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
    .map(({ c }) => c);
}

// The notice above the cards: {kind: "error" | "calm" | "banner" | "hint", text, retry} or null.
// Red ("error") only when something failed and a retry may help; nothing found is calm.
export function lookupNotice(status, data) {
  if (status === 0) return { kind: "error", text: "The local server does not answer.", retry: true };
  if (status !== 200) {
    const text = typeof data.detail === "string" ? data.detail : "The lookup was not accepted.";
    return { kind: "error", text, retry: status >= 500 };
  }
  if (data.error) return { kind: "error", text: data.error, retry: true };
  if (data.banner) return { kind: "banner", text: data.banner, retry: false };
  if (data.message) return { kind: "calm", text: data.message, retry: false };
  if (data.suggested && data.candidates.length) {
    return {
      kind: "hint",
      text: "Suggestions from the model's knowledge; each one is checked against the SEC list. Pick one:",
      retry: false,
    };
  }
  return null;
}
