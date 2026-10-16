// Analysis cards: one per evaluator, grey while waiting, coloured with the
// verdict in words once it finishes, outlined in red if it failed. Colours
// support the words; they never replace them.

const VERDICT_CLASS = {
  STRONG_CASE: "good",
  CONDITIONAL_CASE: "fair",
  INSUFFICIENT_DATA: "unclear",
  WEAK_CASE: "weak",
  RED_FLAGGED: "bad",
  STRONG: "good",
  ADEQUATE: "fair",
  WEAK: "weak",
  RED_FLAG: "bad",
};

export function verdictClass(code) {
  return VERDICT_CLASS[code] || "pending";
}

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

export function verdictBadge(verdictText, code) {
  return el("span", `badge verdict-${verdictClass(code)}`, verdictText);
}

// A card for an item that has started: {key, label, text (its question)}.
export function createCard(container, { key, label, text }) {
  const card = el("article", "card is-waiting");
  card.dataset.key = key;
  card.append(el("h3", "card-title", label));
  if (text) card.append(el("p", "card-question", text));
  const status = el("div", "card-status");
  status.append(el("span", "pulse"), el("span", "card-status-text", "Working…"));
  card.append(status);
  card.append(el("p", "card-summary"));
  container.append(card);
  return card;
}

// Update a card from a progress event of status done, failed or skipped.
export function updateCard(card, event) {
  card.classList.remove("is-waiting");
  const status = card.querySelector(".card-status");
  const summary = card.querySelector(".card-summary");
  status.replaceChildren();
  if (event.status === "done") {
    card.classList.add("is-done", `verdict-${verdictClass(event.verdict)}`);
    status.append(verdictBadge(event.verdict_text || "Done", event.verdict));
    if (event.confidence_text) {
      status.append(el("span", "confidence", `${event.confidence_text} confidence`));
    }
    summary.textContent = event.text || "";
  } else if (event.status === "failed") {
    card.classList.add("is-failed");
    status.append(el("span", "badge badge-failed", "Failed"));
    summary.textContent = "This analysis failed; the overall verdict will rest on the others.";
    summary.title = event.text || "";
  } else if (event.status === "skipped") {
    card.classList.add("is-skipped");
    status.append(el("span", "badge badge-skipped", "Not relevant here"));
    summary.textContent = event.text || "";
  }
}
