// Follows a run's server-sent events until its final "run" event.
//
// Event shape (core/progress.py, ProgressEvent):
//   {stage, status, key, label, text, verdict, verdict_text, confidence_text, cost_usd}
// The server replays every event from the start, so following again after a
// page reload rebuilds the same picture.

export function followRun(url, onEvent, onEnd) {
  const source = new EventSource(url);
  let ended = false;
  source.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.stage === "run") {
      ended = true;
      source.close(); // otherwise EventSource reconnects and replays the run
      onEnd(event);
    } else {
      onEvent(event);
    }
  };
  source.onerror = () => {
    if (ended) return;
    source.close();
    onEnd({ stage: "run", status: "failed", text: "Lost the connection to the local server." });
  };
  return () => source.close();
}
