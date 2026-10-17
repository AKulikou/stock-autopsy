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
