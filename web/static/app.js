// The page: choose a company -> data and live analysis -> result (docs/web_ui.md).

import { createCard, el, setCardState, updateCard, verdictBadge, verdictClass } from "./cards.js";
import { followRun } from "./events.js";
import {
  STATE_TEXT,
  afterLostConnection,
  afterRestored,
  afterRunFailed,
  liveHeading,
  outcomeWords,
  tabTitle,
} from "./live.js";
import { costMarkdown, glossaryMarkdown } from "./collapsed.js";
import { candidateCard, lookupNotice, orderCandidates } from "./lookup.js";
import { renderMarkdown } from "./markdown.js";
import { ORIGINAL, languageOptions, needsTranslation, saveTarget, tabKeyTarget, tabLabel } from "./reporttabs.js";

const $ = (id) => document.getElementById(id);
const VIEWS = ["input-view", "live-view", "result-view"];
let timer = null;
let languages = [];
let defaultLanguage = null;
let analysts = []; // [{key, label, waits_for}] in the order a run starts them
let subject = null; // {name, ticker, relatedTo} of the run on screen

function show(view) {
  for (const id of VIEWS) $(id).hidden = id !== view;
  window.scrollTo({ top: 0 });
  if (view === "input-view") {
    document.title = tabTitle(null);
    loadRecent();
  }
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

// kind: "error" (red, with a retry button when a retry may help), "banner", "calm" or "hint".
function inputMessage(text, kind = "calm", retry = null) {
  const box = $("input-message");
  box.className = `notice notice-${kind}${kind === "error" ? " is-error" : ""}`;
  box.replaceChildren();
  if (text) box.append(el("p", null, text));
  if (retry) {
    const buttons = el("div", "buttons");
    const again = el("button", "secondary", "Try again");
    again.type = "button";
    again.addEventListener("click", retry);
    buttons.append(again);
    box.append(buttons);
  }
  box.hidden = !text;
}

function candidateButton(c, relatedTo) {
  const look = candidateCard(c);
  const button = el("button", `candidate secondary is-${look.kind}`);
  button.type = "button";
  const label = el("span", "match-label");
  label.append(el("span", "match-icon", look.icon), document.createTextNode(` ${look.label}`));
  label.firstChild.setAttribute("aria-hidden", "true");
  button.append(label, el("strong", null, c.name));
  if (c.note && c.note !== c.relation) button.append(el("span", "muted", c.note));
  if (look.financialNote) button.append(el("span", "sector-note", look.financialNote));
  if (!look.canRun) {
    // No 10-K or 10-Q reports: a run would only pay for an empty data pack.
    button.disabled = true;
    button.append(el("span", "unsupported-note", `Cannot be analyzed. ${c.unsupported}`));
  } else {
    button.append(el("span", "candidate-action", "Analyze"));
    const related = look.kind === "related" ? relatedTo : null;
    button.addEventListener("click", () => analyze(c.ticker, c.name, related));
  }
  return button;
}

async function find(query) {
  $("candidates").replaceChildren();
  inputMessage("");
  if (!query.trim()) return;
  $("find").disabled = true;
  const { status, data } = await request("POST", "/api/resolve", { query }).catch(() => ({ status: 0, data: {} }));
  $("find").disabled = false;
  const notice = lookupNotice(status, data);
  if (notice) inputMessage(notice.text, notice.kind, notice.retry ? () => find(query) : null);
  if (status !== 200) return;
  for (const c of orderCandidates(data.candidates)) {
    $("candidates").append(candidateButton(c, data.query_name || query.trim()));
  }
  // A ticker typed exactly: no need to pick.
  if (!data.suggested && data.candidates.length === 1 && !data.candidates[0].unsupported) {
    $("candidates").firstChild.focus();
  }
}

async function analyze(ticker, name, relatedTo = null) {
  const body = { ticker, name, related_to: relatedTo };
  const { status, data } = await request("POST", "/api/runs", body).catch(() => ({ status: 0, data: {} }));
  if (status === 202) {
    startLive(data.run_id, 0, null, { name, ticker, relatedTo });
  } else if (status === 409 && data.active_run_id) {
    const active = await request("GET", "/api/runs/active").catch(() => ({ data: {} }));
    startLive(data.active_run_id, null, detailText(data),
      { name: active.data.name, ticker: active.data.ticker, relatedTo: active.data.related_to });
  } else {
    inputMessage(status === 0 ? "The local server does not answer." : detailText(data), "error");
  }
}

// Finished analyses the server still holds: a paid result is never only in results/.
async function loadRecent() {
  const { status, data } = await request("GET", "/api/runs/recent").catch(() => ({ status: 0, data: {} }));
  const runs = status === 200 ? data.runs.filter((r) => r.analyzed) : [];
  $("recent").hidden = !runs.length;
  $("recent-list").replaceChildren(...runs.map((run) => {
    const button = el("button", "candidate secondary");
    button.type = "button";
    button.append(el("strong", null, run.company), el("span", "muted", `${capitalize(run.outcome)} · finished ${run.finished}`));
    button.addEventListener("click", () => openResult(run.run_id));
    return button;
  }));
}

async function openResult(runId) {
  subject = null;
  const { status, data } = await request("GET", `/api/runs/${runId}/result`).catch(() => ({ status: 0, data: {} }));
  if (status === 200 && data.analyzed) {
    renderResult(runId, data);
    show("result-view");
  } else {
    inputMessage(status === 0 ? "The local server does not answer." : data.error || detailText(data), "error");
  }
}

// ---------- 2-3. Live ----------

function setStage(id, state, text) {
  const stage = $(id);
  if (!stage) return;
  stage.className = `stage is-${state}`;
  stage.dataset.state = state;
  const target = stage.querySelector(".stage-text");
  if (state === "running" && typeof text === "string") stage.dataset.runningText = text;
  target.replaceChildren();
  if (typeof text === "string") target.textContent = text;
  else if (text) target.append(text);
}

// Move every card and stage of the live view to its next state (live.js).
function applyLive(next) {
  for (const node of $("live-view").querySelectorAll("[data-state]")) {
    const state = next(node.dataset.state);
    if (state === node.dataset.state) continue;
    const text = STATE_TEXT[state] || (node.dataset.runningText ?? "Working…");
    if (node.classList.contains("card")) setCardState(node, state, text);
    else setStage(node.id, state, text);
  }
}

function liveNotice(text, { isError = false, buttons = [] } = {}) {
  const box = $("live-message");
  box.classList.toggle("is-error", isError);
  box.replaceChildren(el("p", null, text));
  if (buttons.length) {
    const row = el("div", "buttons");
    for (const [label, action] of buttons) {
      const button = el("button", "secondary", label);
      button.type = "button";
      button.addEventListener("click", action);
      row.append(button);
    }
    box.append(row);
  }
  box.hidden = false;
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
      setStage("stage-pack", event.status === "done" ? "done" : "failed", capitalize(event.text) + ".");
      break;
    case "dcf":
      // "not_computed" is a data limitation (no revenue, no share count), not a failure.
      setStage("stage-dcf", event.status, event.text || "");
      break;
    case "evaluator": {
      let card = cards.querySelector(`[data-key="${CSS.escape(event.key)}"]`);
      if (event.status === "started") {
        if (!card) card = createCard(cards, { key: event.key, label: event.label });
        setCardState(card, "running", "Working…");
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
  for (const a of analysts) createCard($("cards"), { key: a.key, label: a.label, waitsFor: a.waits_for });
  setStage("stage-fetch", "running", "Fetching the company's filings and price…");
  setStage("stage-pack", "waiting", "Waits for the filings.");
  setStage("stage-dcf", "waiting", "Waits for the valuation assumptions.");
  setStage("stage-committee", "waiting", "Waits for the analysts.");
  setStage("stage-number_check", "waiting", "Runs last, by code.");
  $("live-message").hidden = true;
}

function startLive(runId, elapsedS, note, who = {}) {
  subject = who;
  resetLive();
  show("live-view");
  $("live-heading").textContent = liveHeading(who);
  document.title = tabTitle(who.ticker || who.name, "analyzing…");
  startTimer(elapsedS);
  if (note) liveNotice(note);
  const follow = followRun(runId, {
    onEvent: onProgress,
    onEnd: (event) => finishRun(runId, event),
    onConnection: (state) => {
      if (state === "lost") {
        // The server may still be working: keep the timer and the cards, offer no new start.
        applyLive(afterLostConnection);
        liveNotice("Lost the connection to the local server; reconnecting. The analysis may still be running there.");
      } else if (state === "restored") {
        applyLive(afterRestored);
        $("live-message").hidden = true;
      } else if (state === "gave_up") {
        liveNotice("Lost the connection; the analysis may still be running on the server.", {
          buttons: [["Check again", () => follow.retry()]],
        });
      }
    },
  });
}

function stoppedRun(text) {
  clearInterval(timer);
  document.title = tabTitle(subject?.ticker || subject?.name, "stopped");
  applyLive(afterRunFailed);
  liveNotice(text, { isError: true, buttons: [["Choose another company", () => show("input-view")]] });
}

async function finishRun(runId, event) {
  if (event.status !== "done") {
    stoppedRun(event.text || "The analysis stopped on the server.");
    return;
  }
  const { status, data } = event.result
    ? { status: 200, data: event.result }
    : await request("GET", `/api/runs/${runId}/result`).catch(() => ({ status: 0, data: {} }));
  if (status === 200 && data.analyzed) {
    clearInterval(timer);
    renderResult(runId, data);
    show("result-view");
  } else if (status === 200) {
    stoppedRun(data.error || "The analysis stopped on the server.");
  } else {
    clearInterval(timer);
    const text = status === 0 ? "The analysis finished, but the local server does not answer." : detailText(data);
    liveNotice(text, { isError: true, buttons: [["Check again", () => finishRun(runId, event)]] });
  }
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
    el("p", "verdict-label", `${view.company_heading || view.company} · data as of ${view.as_of}`),
    el("p", "verdict-label", `Financial statements to ${view.statements_to || "an unknown date"}`),
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
  document.title = tabTitle(subject?.ticker || view.company, outcomeWords(view));
  const root = $("result");
  root.replaceChildren();
  const english = el("div", "report-pane");
  english.id = "pane-original";
  english.setAttribute("role", "tabpanel");
  english.setAttribute("aria-labelledby", "tab-original");
  const c = view.committee;
  if (c.ok) {
    english.append(banner(view));
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
    english.append(grid);
  } else {
    english.append(el("div", "notice is-error", c.text));
  }

  english.append(el("h2", null, "Number check"));
  english.append(numberCounter(view.number_check));
  if (view.number_check.absent_as_zero.length) {
    english.append(el("p", null, "Unknown values stated as zero or none (the filings do not say so):"), list(view.number_check.absent_as_zero));
  }
  english.append(el("p", "muted", `${view.number_check.prose_unsourced} of ${view.number_check.prose_numbers} numbers in the analysts' prose have no source in the data; treat them as unverified.`));

  english.append(el("h2", null, "The analysts"));
  for (const card of view.evaluators) english.append(evaluatorDetails(card));

  english.append(el("h2", null, "Valuation calculated by Stock Autopsy"));
  const v = view.valuation;
  const table = el("table", "kv");
  const rows = [...v.multiples.map((m) => [m.label, m.value])];
  if (v.computed) {
    rows.push(["Price", v.price], ...v.per_share.map((p) => [`DCF value per share, ${p.label} case`, p.value]));
    rows.push([v.implied_growth_label, v.implied_growth]);
    if (v.implied_return) rows.push(["Yearly return if the base case comes true", v.implied_return]);
  }
  for (const [label, value] of rows) {
    const tr = el("tr");
    tr.append(el("td", null, label), el("td", null, value));
    table.append(tr);
  }
  english.append(table);
  if (!v.computed) english.append(el("p", "muted", `DCF not computed: ${v.reason}`));

  english.append(el("h2", null, "Data quality"));
  english.append(view.data_quality.length ? list(view.data_quality) : el("p", "muted", "No issues recorded."));
  const total = `Estimated API cost of this run: $${view.cost_usd.toFixed(2)}, ${Math.round(view.duration_s / 60)} minutes.`;
  english.append(el("p", "muted", total));
  // Collapsed, as at the end of report.md: the cost per call and the glossary of the terms used.
  const blocks = el("div", "markdown collapsed-blocks");
  blocks.innerHTML = renderMarkdown([costMarkdown(view.cost, total), glossaryMarkdown(view.glossary)]
    .filter(Boolean).join("\n\n")); // escapes all text; raw HTML is never rendered
  english.append(blocks);

  const tabs = reportTabs(runId, english);
  root.append(tabs.toolbar, english);
  for (const t of view.translations || []) {
    tabs.add(t.language, { code: t.code, label: t.label, download_label: `Save report in ${t.language} (.md)` });
  }
}

// ---------- 5. Report tabs: the English report and its translations ----------

function tabButton(key, text, controls) {
  const tab = el("button", "tab", text);
  tab.type = "button";
  tab.id = `tab-${key}`;
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-controls", controls);
  return tab;
}

// One toolbar at the top of the result: the tabs, the language picker, Translate and Save.
function reportTabs(runId, englishPane) {
  const translations = new Map(); // language -> {code, label, download_label, markdown?, note?}
  const panes = new Map([[ORIGINAL, englishPane]]);
  const toolbar = el("div", "report-toolbar");
  const tablist = el("div", "tabs");
  tablist.setAttribute("role", "tablist");
  tablist.setAttribute("aria-label", "Report language");
  const save = el("a", "download");
  save.setAttribute("download", "");
  const select = el("select");
  select.setAttribute("aria-label", "Language of the translation");
  for (const language of languageOptions(languages, defaultLanguage)) {
    const option = el("option", null, language.label);
    option.value = language.value;
    option.selected = language.selected;
    select.append(option);
  }
  const translate = el("button", "secondary", "Translate");
  translate.type = "button";
  const picker = el("div", "translate-form");
  picker.append(select, translate);
  const status = el("p", "muted translate-status");
  status.setAttribute("aria-live", "polite");
  status.textContent = "Translate: a machine translation, about 0.03 USD and up to a minute; every number is "
    + "checked against the English report.";
  const actions = el("div", "toolbar-actions");
  actions.append(picker, save);
  const row = el("div", "toolbar-row");
  row.append(tablist, actions);
  toolbar.append(row, status);
  let open = ORIGINAL;

  const allTabs = () => [...tablist.querySelectorAll('[role="tab"]')];

  function show(key, focus = false) {
    open = key;
    for (const tab of allTabs()) {
      const selected = tab.dataset.key === key;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && focus) tab.focus();
    }
    for (const [k, pane] of panes) pane.hidden = k !== key;
    const target = saveTarget(runId, key, translations);
    save.href = target.href;
    save.textContent = target.label;
    if (key !== ORIGINAL && !translations.get(key).markdown) load(key);
  }

  function fill(language) {
    const t = translations.get(language);
    const notes = el("div", "notice notice-calm translation-notes", t.note);
    const body = el("div", "markdown translated-report");
    body.lang = t.code;
    body.innerHTML = renderMarkdown(t.markdown); // escapes all text; raw HTML is never rendered
    panes.get(language).replaceChildren(notes, body);
  }

  async function load(language) {
    // A copy on disk (made earlier): the server returns it without translating again.
    const pane = panes.get(language);
    pane.replaceChildren(el("p", "muted", "Loading the translation…"));
    const { status: code, data } = await request("POST", `/api/runs/${runId}/translation`, { language })
      .catch(() => ({ status: 0, data: {} }));
    if (code !== 200) {
      pane.replaceChildren(el("div", "notice is-error", code === 0 ? "The local server does not answer." : detailText(data)));
      return;
    }
    translations.set(language, data);
    fill(language);
  }

  function add(language, translation) {
    translations.set(language, translation);
    if (!panes.has(language)) {
      const pane = el("div", "report-pane");
      pane.id = `pane-${translation.code}`;
      pane.setAttribute("role", "tabpanel");
      pane.setAttribute("aria-labelledby", `tab-${translation.code}`);
      pane.hidden = true;
      [...panes.values()].at(-1).after(pane);
      panes.set(language, pane);
      const tab = tabButton(translation.code, tabLabel(language, translations), pane.id);
      tab.dataset.key = language;
      tab.addEventListener("click", () => show(language));
      tablist.append(tab);
    }
    if (translation.markdown) fill(language);
    show(open);
  }

  tablist.addEventListener("keydown", (event) => {
    const tabs = allTabs();
    const target = tabKeyTarget(event.key, tabs.findIndex((tab) => tab.dataset.key === open), tabs.length);
    if (target === null) return;
    event.preventDefault();
    show(tabs[target].dataset.key, true);
  });

  translate.addEventListener("click", async () => {
    const language = select.value;
    if (!needsTranslation(language, translations)) {
      show(language, true); // translated already: open its tab, never pay twice
      toolbar.scrollIntoView({ block: "start" });
      return;
    }
    translate.disabled = true;
    select.disabled = true;
    status.classList.remove("is-error");
    status.textContent = "Translating the report section by section…";
    const { status: code, data } = await request("POST", `/api/runs/${runId}/translation`, { language })
      .catch(() => ({ status: 0, data: {} }));
    translate.disabled = false;
    select.disabled = false;
    if (code !== 200) {
      status.classList.add("is-error");
      status.textContent = code === 0 ? "The local server does not answer." : detailText(data);
      return;
    }
    status.textContent = `Translated into ${data.label}.`;
    add(language, data);
    show(language, true);
    toolbar.scrollIntoView({ block: "start" });
  });

  const original = tabButton(ORIGINAL, tabLabel(ORIGINAL, translations), englishPane.id);
  original.dataset.key = ORIGINAL;
  original.addEventListener("click", () => show(ORIGINAL));
  tablist.append(original);
  show(ORIGINAL);
  return { toolbar, add };
}

// ---------- Start ----------

async function init() {
  const { data } = await request("GET", "/api/options");
  languages = data.languages || [];
  analysts = data.analysts || [];
  defaultLanguage = data.default_language;
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
  if (active.data.run_id) {
    startLive(active.data.run_id, active.data.elapsed_s, null,
      { name: active.data.name, ticker: active.data.ticker, relatedTo: active.data.related_to });
  }
  else loadRecent();
}

init();
