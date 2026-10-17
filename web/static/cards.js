// Analysis cards: one per analyst, shown from the start of a run. Each look has its
// own mark, and none reuses the verdict colours for anything but a verdict (M9):
//
//   waiting    dimmed, a hollow grey dot, "Waits for ..."
//   running    a dot pulsing in the page accent, a thin moving accent line on top
//   done       no verdict (the valuation assumptions): an accent check mark and "Done"
//   verdict    a steady lamp and the card top in the verdict colour, the verdict in words
//   failed     a red outline and "Failed"
//
// Colours support the words; they never replace them.

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

// A verdict word standing alone starts with a capital ("Adequate"); the same words stay
// lower case inside sentences (reporting/wording.py keeps them so), M12.
export function badgeLabel(text) {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

export function verdictBadge(verdictText, code) {
  return el("span", `badge verdict-${verdictClass(code)}`, badgeLabel(verdictText));
}

// What a finished, failed or skipped item looks like: {state, verdictClass, mark, badge}.
// A step without a verdict is "done" in the accent, never the grey of a pending item (M10).
export function finishedLook(event) {
  if (event.status === "failed") return { state: "failed", mark: "failed", badge: "Failed" };
  if (event.status === "skipped") return { state: "skipped", mark: "hollow", badge: "Not relevant here" };
  if (event.verdict) {
    return { state: "done", verdictClass: verdictClass(event.verdict), mark: "lamp", badge: event.verdict_text };
  }
  return { state: "done", verdictClass: "done", mark: "check", badge: null };
}

const MARKS = { running: "pulse", hollow: "status-mark", lamp: "lamp", check: "check-mark", failed: "status-mark" };

function mark(kind) {
  return el("span", MARKS[kind], kind === "check" ? "✓" : null);
}

// A card in the waiting look, before its analyst starts: {key, label, waitsFor}.
export function createCard(container, { key, label, waitsFor }) {
  const card = el("article", "card is-waiting");
  card.dataset.key = key;
  card.dataset.state = "waiting";
  card.append(el("h3", "card-title", label));
  const status = el("div", "card-status");
  status.append(mark("hollow"), el("span", "card-status-text", waitsFor ? `Waits for ${waitsFor}.` : "Waiting."));
  card.append(status, el("p", "card-summary"));
  container.append(card);
  return card;
}

// The card's state with its words: running ("Working…"), unknown or stopped (live.js).
export function setCardState(card, state, text) {
  card.classList.remove(`is-${card.dataset.state}`);
  card.classList.add(`is-${state}`);
  card.dataset.state = state;
  const status = card.querySelector(".card-status");
  status.replaceChildren(mark(state === "running" ? "running" : "hollow"), el("span", "card-status-text", text));
}

// Update a card from a progress event of status done, failed or skipped.
export function updateCard(card, event) {
  const look = finishedLook(event);
  card.classList.remove(`is-${card.dataset.state}`);
  card.classList.add(`is-${look.state}`);
  if (look.verdictClass) card.classList.add(`verdict-${look.verdictClass}`);
  card.dataset.state = look.state;
  const status = card.querySelector(".card-status");
  const summary = card.querySelector(".card-summary");
  status.replaceChildren(mark(look.mark));
  if (look.state === "done") {
    if (look.badge) status.append(verdictBadge(look.badge, event.verdict));
    else status.append(el("span", "card-status-text done-text", "Done"));
    if (event.confidence_text) {
      status.append(el("span", "confidence", `${event.confidence_text} confidence`));
    }
    summary.textContent = event.text || "";
  } else if (look.state === "failed") {
    status.append(el("span", "badge badge-failed", look.badge));
    summary.textContent = "This analysis failed; the overall verdict will rest on the others.";
    summary.title = event.text || "";
  } else {
    status.append(el("span", "badge badge-skipped", look.badge));
    summary.textContent = event.text || "";
  }
}
