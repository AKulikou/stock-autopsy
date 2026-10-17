// The finished looks of a card (web/static/cards.js, M9 and M10).
import assert from "node:assert/strict";
import { test } from "node:test";

import { finishedLook } from "../../web/static/cards.js";

test("a step without a verdict is done in the accent, not pending grey", () => {
  const look = finishedLook({ status: "done", verdict: null, text: "assumptions for the bear, base and bull cases" });
  assert.deepEqual(look, { state: "done", verdictClass: "done", mark: "check", badge: null });
});

test("a verdict lights a steady lamp in its colour", () => {
  const look = finishedLook({ status: "done", verdict: "ADEQUATE", verdict_text: "adequate" });
  assert.equal(look.verdictClass, "fair");
  assert.equal(look.mark, "lamp");
});

test("a failed or skipped analyst is never shown as done", () => {
  assert.equal(finishedLook({ status: "failed" }).state, "failed");
  assert.equal(finishedLook({ status: "skipped" }).state, "skipped");
});
