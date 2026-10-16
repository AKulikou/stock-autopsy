// The page: choose a company -> data and live analysis -> result (docs/web_ui.md).

import { createCard, el, updateCard, verdictBadge, verdictClass } from "./cards.js";
import { followRun } from "./events.js";

const $ = (id) => document.getElementById(id);
const VIEWS = ["input-view", "live-view", "result-view"];
let timer = null;

function show(view) {
  for (const id of VIEWS) $(id).hidden = id !== view;
  window.scrollTo({ top: 0 });
}

async function request(method, url, body) {
  const response = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  return { status: response.status, data };
}

function detailText(data) {
  return typeof data.detail === "string" ? data.detail : "The request was not accepted.";
}

function capitalize(text) {
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}

// ---------- 1. Choose a company ----------

function inputMessage(text, isError = false) {
  const box = $("input-message");
  box.classList.toggle("is-error", isError);
  box.textContent = text || "";
  box.hidden = !text;
}

async function find(query) {
  $("candidates").replaceChildren();
  inputMessage("");
  if (!query.trim()) return;
  $("find").disabled = true;
  const { status, data } = await request("POST", "/api/resolve", { query }).catch(() => ({ status: 0, data: {} }));
  $("find").disabled = false;
  if (status !== 200) {
    inputMessage(status === 0 ? "The local server does not answer." : detailText(data), true);
    return;
  }
  if (data.message) inputMessage(data.message, !data.candidates.length);
  if (data.suggested && data.candidates.length) {
    inputMessage("Suggestions from the model's knowledge; each one is checked against the SEC list. Pick one:");
  }
  for (const c of data.candidates) {
    const button = el("button", "candidate secondary");
    button.type = "button";
    button.append(el("strong", null, c.name));
    if (c.note) button.append(el("span", "muted", c.note));
    button.append(el("span", null, "Analyze"));
    button.addEventListener("click", () => analyze(c.ticker));
    $("candidates").append(button);
  }
  // A ticker typed exactly: no need to pick.
  if (!data.suggested && data.candidates.length === 1) {
    $("candidates").firstChild.focus();
  }
}

async function analyze(ticker) {
  const { status, data } = await request("POST", "/api/runs", { ticker }).catch(() => ({ status: 0, data: {} }));
  if (status === 202) {
    startLive(data.run_id, 0);
  } else if (status === 409 && data.active_run_id) {
    startLive(data.active_run_id, null, detailText(data));
  } else {
    inputMessage(status === 0 ? "The local server does not answer." : detailText(data), true);
  }
}

// ---------- 2-3. Live ----------

function setStage(id, state, text) {
  const stage = $(id);
  if (!stage) return;
  stage.className = `stage is-${state}`;
  const target = stage.querySelector(".stage-text");
  target.replaceChildren();
  if (typeof text === "string") target.textContent = text;
  else if (text) target.append(text);
}

function startTimer(elapsedS) {
  clearInterval(timer);
  if (elapsedS === null) {
    $("elapsed").textContent = "";
    return;
  }
  const started = Date.now() - elapsedS * 1000;
  const tick = () => {
    const s = Math.round((Date.now() - started) / 1000);
    $("elapsed").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };
  tick();
  timer = setInterval(tick, 1000);
}

function onProgress(event) {
  const cards = $("cards");
  switch (event.stage) {
    case "fetch":
      if (event.status === "done") {
        setStage("stage-fetch", "done", `Received from the SEC and the price feed (${event.text}).`);
        setStage("stage-pack", "running", "Building the data pack…");
      } else if (event.status === "failed") {
        setStage("stage-fetch", "failed", event.text);
      }
      break;
    case "pack":
      setStage("stage-pack", "done", capitalize(event.text) + ".");
      break;
    case "dcf":
      setStage("stage-dcf", event.status === "done" ? "done" : "failed", event.text || "");
      break;
    case "evaluator": {
      let card = cards.querySelector(`[data-key="${CSS.escape(event.key)}"]`);
      if (event.status === "started") {
        if (!card) createCard(cards, { key: event.key, label: event.label });
        if (event.key === "valuation_assumptions") setStage("stage-dcf", "waiting", "Waits for the valuation assumptions.");
      } else {
        if (!card) card = createCard(cards, { key: event.key, label: event.label });
        updateCard(card, event);
      }
      break;
    }
    case "committee":
      if (event.status === "started") {
        setStage("stage-committee", "running", "Weighing the analysts' reports against each other…");
      } else if (event.status === "done") {
        const text = el("span");
        text.append(verdictBadge(event.verdict_text, event.verdict), ` ${event.text || ""}`);
        setStage("stage-committee", "done", text);
      } else {
        setStage("stage-committee", "failed", "No conclusion: the committee did not run.");
      }
      break;
    case "number_check":
      setStage("stage-number_check", "done", capitalize(event.text) + ".");
      break;
    default:
      break;
  }
}

function resetLive() {
  $("cards").replaceChildren();
  setStage("stage-fetch", "running", "Fetching the company's filings and price…");
  setStage("stage-pack", "waiting", "Waits for the filings.");
  setStage("stage-dcf", "waiting", "Waits for the valuation assumptions.");
  setStage("stage-committee", "waiting", "Waits for the analysts.");
  setStage("stage-number_check", "waiting", "Runs last, by code.");
  $("live-message").hidden = true;
}

function startLive(runId, elapsedS, note) {
  resetLive();
  show("live-view");
  startTimer(elapsedS);
  if (note) {
    $("live-message").textContent = note;
    $("live-message").classList.remove("is-error");
    $("live-message").hidden = false;
  }
  followRun(`/api/runs/${runId}/events`, onProgress, () => finishRun(runId));
}

async function finishRun(runId) {
  clearInterval(timer);
  const { status, data } = await request("GET", `/api/runs/${runId}/result`).catch(() => ({ status: 0 }));
  if (status !== 200 || !data.analyzed) {
    const box = $("live-message");
    box.classList.add("is-error");
    box.replaceChildren(el("p", null, data?.error || "The analysis stopped unexpectedly."));
    const back = el("button", "secondary", "Choose another company");
    back.type = "button";
    back.addEventListener("click", () => show("input-view"));
    box.append(back);
    box.hidden = false;
    return;
  }
  renderResult(runId, data);
  show("result-view");
}

// ---------- 4. Result ----------

function panel(title, wide = false) {
  const node = el("section", wide ? "panel wide" : "panel");
  node.append(el("h3", null, title));
  return node;
}

function list(items, ordered = false) {
  const node = el(ordered ? "ol" : "ul");
  for (const item of items) node.append(el("li", null, item));
  return node;
}

function banner(view) {
  const c = view.committee;
  const box = el("div", `verdict-banner verdict-${verdictClass(c.verdict)}`);
  const [short, meaning] = c.verdict_text.split(": ");
  box.append(
    el("p", "verdict-label", `${view.company} · data as of ${view.as_of}`),
    el("p", "verdict-text", short),
    el("p", "verdict-meaning", capitalize(meaning || "") + "."),
  );
  const confidence = el("p");
  confidence.append(el("strong", null, `${capitalize(c.confidence_text)} confidence. `), c.confidence_reason);
  box.append(confidence, el("p", "verdict-summary", c.headline));
  if (c.price_assumes) box.append(el("p", "price-assumes", `What the price assumes: ${c.price_assumes}`));
  box.append(el("p", "disclaimer", "This is an assessment of the evidence, not advice to buy or sell."));
  return box;
}

function numberCounter(check) {
  const node = el("div", "counter");
  node.append(
    el("span", "match", `${check.match} of ${check.data_claims} quoted numbers match the data pack`),
    el("span", "computed", `${check.computed} of ${check.computed_claims} calculations reproduced by code`),
    el("span", "weak", `${check.weak} found only somewhere in a table`),
    el("span", "wrong", `${check.wrong} not in the cited data`),
  );
  return node;
}

function evaluatorDetails(card) {
  const details = el("details", card.ok ? `lens-details verdict-${verdictClass(card.verdict)}` : "lens-details is-failed");
  const summary = el("summary");
  const head = el("div", "lens-head");
  head.append(el("strong", null, card.name));
  if (card.verdict_text) {
    head.append(verdictBadge(card.verdict_text, card.verdict), el("span", "confidence", `${card.confidence_text} confidence`));
  }
  if (!card.ok) head.append(el("span", "badge badge-failed", "Failed"));
  summary.append(head, el("span", null, card.ok ? card.headline : card.text));
  details.append(summary);
  if (!card.ok) return details;
  const body = el("div", "lens-body");
  if (card.summary) body.append(el("p", null, card.summary));
  for (const d of card.details) body.append(el("p", "detail-label", d.label), el("p", null, d.text));
  if (card.biggest_unknown) body.append(el("p", "detail-label", "Biggest unknown"), el("p", null, card.biggest_unknown));
  if (card.claims.length) {
    body.append(el("p", "detail-label", "Claims, each checked by code where it quotes a number"));
    const claims = el("ul", "claims");
    for (const c of card.claims) {
      const item = el("li", `claim check-${c.check}`, c.statement);
      const note = [c.tag, c.check_text, c.basis].filter(Boolean).join(" · ");
      item.append(el("small", null, note));
      claims.append(item);
    }
    body.append(claims);
  }
  details.append(body);
  return details;
}

function renderResult(runId, view) {
  const root = $("result");
  root.replaceChildren();
  const c = view.committee;
  if (c.ok) {
    root.append(banner(view));
    const grid = el("div", "result-grid");
    const forPanel = panel("For");
    forPanel.append(list(c.reasons_for));
    const againstPanel = panel("Against");
    againstPanel.append(list(c.reasons_against));
    const unknown = panel("What we do not know");
    unknown.append(list(c.unknowns));
    const watch = panel("What to watch");
    watch.append(list(c.watch.map((w) => `${w.item}: ${w.threshold}`)));
    grid.append(forPanel, againstPanel, unknown, watch);
    if (c.conditions.length) {
      const conditions = panel("Conditions for the case", true);
      conditions.append(list(c.conditions));
      grid.append(conditions);
    }
    root.append(grid);
  } else {
    root.append(el("div", "notice is-error", c.text));
  }

  root.append(el("h2", null, "Number check"));
  root.append(numberCounter(view.number_check));
  if (view.number_check.absent_as_zero.length) {
    root.append(el("p", null, "Unknown values stated as zero or none (the filings do not say so):"), list(view.number_check.absent_as_zero));
  }
  root.append(el("p", "muted", `${view.number_check.prose_unsourced} of ${view.number_check.prose_numbers} numbers in the analysts' prose have no source in the data; treat them as unverified.`));

  root.append(el("h2", null, "The analysts"));
  for (const card of view.evaluators) root.append(evaluatorDetails(card));

  root.append(el("h2", null, "Valuation computed by Python"));
  const v = view.valuation;
  const table = el("table", "kv");
  const rows = [...v.multiples.map((m) => [m.label, m.value])];
  if (v.computed) {
    rows.push(["Price", v.price], ...v.per_share.map((p) => [`DCF value per share, ${p.label} case`, p.value]));
    rows.push(["Revenue growth the price implies", v.implied_growth]);
    if (v.implied_return) rows.push(["Yearly return if the base case comes true", v.implied_return]);
  }
  for (const [label, value] of rows) {
    const tr = el("tr");
    tr.append(el("td", null, label), el("td", null, value));
    table.append(tr);
  }
  root.append(table);
  if (!v.computed) root.append(el("p", "muted", `DCF not computed: ${v.reason}`));

  root.append(el("h2", null, "Data quality"));
  root.append(view.data_quality.length ? list(view.data_quality) : el("p", "muted", "No issues recorded."));

  root.append(el("h2", null, "Downloads"));
  const downloads = el("div", "downloads");
  for (const d of view.downloads) {
    const link = el("a", "download", d.label);
    link.href = `/api/runs/${runId}/files/${d.kind}`;
    link.setAttribute("download", "");
    downloads.append(link);
  }
  root.append(downloads, el("p", "muted", `Estimated API cost of this run: $${view.cost_usd.toFixed(2)}, ${Math.round(view.duration_s / 60)} minutes.`));
}

// ---------- Start ----------

async function init() {
  const { data } = await request("GET", "/api/options");
  for (const example of data.examples) {
    const chip = el("button", "chip", example.title);
    chip.type = "button";
    chip.addEventListener("click", () => {
      $("query").value = example.query;
      find(example.query);
    });
    $("examples").append(chip);
  }
  $("search").addEventListener("submit", (e) => {
    e.preventDefault();
    find($("query").value);
  });
  $("again").addEventListener("click", () => show("input-view"));
  const active = await request("GET", "/api/runs/active");
  if (active.data.run_id) startLive(active.data.run_id, active.data.elapsed_s);
}

init();
