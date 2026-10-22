// The company lookup's cards and notices (web/static/lookup.js, D2).
import assert from "node:assert/strict";
import { test } from "node:test";

import { candidateCard, lookupNotice, orderCandidates, shortReason } from "../../web/static/lookup.js";

const FOREIGN = "Files Form 20-F (a foreign company): this version reads 10-K and 10-Q reports only.";
const exact = { name: "Coca Cola Co", match_type: "exact", relation: null, share_class: null, unsupported: null };
const related = { name: "Microsoft Corp", match_type: "related", relation: "major investor in OpenAI",
  share_class: null, unsupported: null };
const relatedForeign = { name: "Stellantis N.V.", match_type: "related", relation: "parent of Chrysler",
  share_class: null, unsupported: FOREIGN };

test("an exact match is green with a check mark and can be analyzed", () => {
  assert.deepEqual(candidateCard(exact), { kind: "exact", icon: "✓", label: "Exact match", canRun: true, financialNote: null });
});

test("a related company says how it is related", () => {
  assert.deepEqual(candidateCard(related),
    { kind: "related", icon: "↔", label: "Related: major investor in OpenAI", canRun: true,
      financialNote: null });
});

test("a company that cannot be analyzed is grey and keeps its label and the short reason", () => {
  assert.deepEqual(candidateCard(relatedForeign), {
    kind: "unavailable", icon: "↔", label: "Related: parent of Chrysler · Files Form 20-F", canRun: false,
    financialNote: null,
  });
  assert.equal(candidateCard({ ...exact, unsupported: FOREIGN }).label, "Exact match · Files Form 20-F");
  assert.equal(shortReason("A fund (files fund reports such as N-CSR, not a 10-K): no data."), "A fund");
});

test("share classes of one company are both exact matches, each with its class", () => {
  const a = candidateCard({ ...exact, share_class: "Class A" });
  const c = candidateCard({ ...exact, share_class: "Class C" });
  assert.equal(a.kind, "exact");
  assert.equal(a.label, "Exact match · Class A");
  assert.equal(c.label, "Exact match · Class C");
});

test("a bank keeps its Analyze button and gets a calm note", () => {
  const note = "Bank or financial company: EV, DCF and cash-flow multiples do not fit how banks report; the analysis will say so.";
  const card = candidateCard({ ...exact, name: "Goldman Sachs Group Inc", financial_note: note });
  assert.equal(card.canRun, true);
  assert.equal(card.financialNote, note);
  assert.equal(candidateCard(exact).financialNote, null);
});

test("cards come green, then amber, then grey, keeping the order within each", () => {
  const second = { ...related, name: "Nvidia Corp" };
  const order = orderCandidates([relatedForeign, related, exact, second]).map((c) => c.name);
  assert.deepEqual(order, ["Coca Cola Co", "Microsoft Corp", "Nvidia Corp", "Stellantis N.V."]);
});

test("related companies come under the banner; nothing found is calm; a failure is red with a retry", () => {
  const banner = "OpenAI is a private company and files no reports with the SEC. Related public companies:";
  assert.deepEqual(lookupNotice(200, { candidates: [related], suggested: true, banner }),
    { kind: "banner", text: banner, retry: false });
  assert.equal(lookupNotice(200, { candidates: [], suggested: true, message: "Nothing." }).kind, "calm");
  assert.deepEqual(lookupNotice(200, { candidates: [], suggested: true, error: "The lookup did not answer." }),
    { kind: "error", text: "The lookup did not answer.", retry: true });
  assert.deepEqual(lookupNotice(503, { detail: "The SEC ticker list is not reachable right now." }),
    { kind: "error", text: "The SEC ticker list is not reachable right now.", retry: true });
  assert.equal(lookupNotice(0, {}).retry, true);
  assert.equal(lookupNotice(422, {}).retry, false);
  assert.equal(lookupNotice(200, { candidates: [exact], suggested: false }), null);
  assert.equal(lookupNotice(200, { candidates: [exact], suggested: true }).kind, "hint");
});
