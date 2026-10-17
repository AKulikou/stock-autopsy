// Follows a run's server-sent events until its final "run" event.
//
// Event shape (core/progress.py, ProgressEvent):
//   {stage, status, key, label, text, verdict, verdict_text, confidence_text, cost_usd}
// The server replays every event from the start, so following again after a
// page reload rebuilds the same picture.
//
// A dropped stream is not a failed run (M4, 2026-10-17: the page said "stopped
// unexpectedly" while the server finished the analysis). On an error the stream is
// reopened from the next event (?since=N, no replay) after growing pauses; when
// that keeps failing, the result is asked for until the server stops answering
// "still running" (409). Only the server's final event or its result ends the run.

export const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000];
export const POLL_MS = 5000;
export const POLL_LIMIT = 120; // ten minutes of asking, then the page offers "Check again"
export const FORGOTTEN =
  "The server no longer knows this analysis (was it restarted?). A finished report is in the results folder.";

// handlers: onEvent(event), onEnd(runEvent with an optional .result), onConnection("lost" | "restored" | "gave_up")
// deps (for tests): EventSource, fetch, wait(ms) -> Promise, reconnectDelays, pollMs, pollLimit
export function followRun(runId, handlers, deps = {}) {
  const { onEvent, onEnd, onConnection = () => {} } = handlers;
  const Source = deps.EventSource || globalThis.EventSource;
  const get = deps.fetch || ((url) => globalThis.fetch(url));
  const wait = deps.wait || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
  const delays = deps.reconnectDelays || RECONNECT_DELAYS_MS;
  const pollLimit = deps.pollLimit ?? POLL_LIMIT;
  let seen = 0;
  let failures = 0;
  let lost = false;
  let stopped = false;
  let source = null;

  const end = (event) => {
    if (stopped) return;
    stopped = true;
    if (source) source.close();
    onEnd(event);
  };
  const restored = () => {
    failures = 0;
    if (lost) {
      lost = false;
      onConnection("restored");
    }
  };

  function open() {
    if (stopped) return;
    source = new Source(`/api/runs/${runId}/events?since=${seen}`);
    source.onopen = restored;
    source.onmessage = (message) => {
      const event = JSON.parse(message.data);
      seen += 1;
      restored();
      if (event.stage === "run") end(event);
      else onEvent(event);
    };
    source.onerror = () => {
      if (stopped) return;
      source.close(); // otherwise EventSource reconnects by itself and replays the run
      if (!lost) {
        lost = true;
        onConnection("lost");
      }
      if (failures < delays.length) {
        const delay = delays[failures];
        failures += 1;
        wait(delay).then(open);
      } else {
        poll();
      }
    };
  }

  async function poll() {
    for (let i = 0; i < pollLimit && !stopped; i += 1) {
      let status = 0;
      let data = {};
      try {
        const response = await get(`/api/runs/${runId}/result`);
        status = response.status;
        data = await response.json().catch(() => ({}));
      } catch {
        status = 0; // the server does not answer (yet)
      }
      if (status === 200) {
        end({ stage: "run", status: data.analyzed ? "done" : "failed", text: data.error || null, result: data });
        return;
      }
      if (status === 404) {
        end({ stage: "run", status: "failed", text: FORGOTTEN });
        return;
      }
      if (status === 409) {
        // The server answers and the run goes on: follow it live again.
        failures = 0;
        open();
        return;
      }
      await wait(deps.pollMs ?? POLL_MS);
    }
    if (!stopped) onConnection("gave_up");
  }

  open();
  return {
    stop() {
      stopped = true;
      if (source) source.close();
    },
    // "Check again" after onConnection("gave_up").
    retry() {
      if (!stopped) poll();
    },
  };
}
