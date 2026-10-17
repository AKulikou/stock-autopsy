// The live view's states after a lost connection or a failed run (web/static/live.js, M6).
import assert from "node:assert/strict";
import { test } from "node:test";

import { STATE_TEXT, afterLostConnection, afterRestored, afterRunFailed } from "../../web/static/live.js";

const LIVE = ["done", "running", "running", "waiting", "failed"];

test("after a failure no item still says it is working", () => {
  const after = LIVE.map(afterRunFailed);
  assert.deepEqual(after, ["done", "stopped", "stopped", "not_reached", "failed"]);
  assert.ok(!after.includes("running"));
});

test("a lost connection makes running items unknown, and they run again when it is back", () => {
  const lost = LIVE.map(afterLostConnection);
  assert.deepEqual(lost, ["done", "unknown", "unknown", "waiting", "failed"]);
  assert.deepEqual(lost.map(afterRestored), LIVE);
  assert.equal(afterRunFailed("unknown"), "stopped");
});

test("each new state has words", () => {
  for (const state of ["unknown", "stopped", "not_reached"]) assert.ok(STATE_TEXT[state]);
});

test("the live heading and the tab name the company being analyzed", async () => {
  const { liveHeading, tabTitle, outcomeWords } = await import("../../web/static/live.js");
  assert.equal(liveHeading({ name: "Levi Strauss & Co", ticker: "LEVI" }), "Analyzing Levi Strauss & Co (LEVI)");
  assert.equal(liveHeading({ ticker: "LEVI" }), "Analyzing LEVI");
  assert.equal(liveHeading({}), "Analyzing");
  assert.equal(tabTitle("LEVI", "analyzing…"), "LEVI: analyzing… | Stock Autopsy");
  const view = { committee: { ok: true, verdict_text: "Weak case: the evidence does not support the thesis" } };
  assert.equal(tabTitle("LEVI", outcomeWords(view)), "LEVI: weak case | Stock Autopsy");
  assert.equal(outcomeWords({ committee: { ok: false } }), "no conclusion");
  assert.equal(tabTitle(null), "Stock Autopsy");
});
