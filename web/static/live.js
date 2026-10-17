// What each card and stage of the live view says when the run does not end
// normally (M6). The screen is the only record of where an analysis stopped, so it
// is never reset by itself; instead every item tells the truth:
//
// - the connection is lost (the server may still be working): running items say
//   their status is unknown until the stream is back;
// - the server reports a failure: running items say "Stopped", items that never
//   started say "Not reached", finished items keep their result.
//
// States: waiting, running, done, failed, skipped, unknown, stopped, not_reached.

export const STATE_TEXT = {
  unknown: "Status unknown: reconnecting…",
  stopped: "Stopped: the analysis ended before this step finished.",
  not_reached: "Not reached.",
};

export function afterLostConnection(state) {
  return state === "running" ? "unknown" : state;
}

export function afterRestored(state) {
  return state === "unknown" ? "running" : state;
}

export function afterRunFailed(state) {
  if (state === "running" || state === "unknown") return "stopped";
  if (state === "waiting") return "not_reached";
  return state;
}
