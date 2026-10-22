// followRun (web/static/events.js) with a fake EventSource and a fake fetch:
// a dropped stream is followed again, never reported as a failed run.
import assert from "node:assert/strict";
import { test } from "node:test";

import { FORGOTTEN, followRun } from "../../web/static/events.js";

class FakeSource {
  static opened = [];
  constructor(url) {
    this.url = url;
    this.closed = false;
    FakeSource.opened.push(this);
  }
  close() {
    this.closed = true;
  }
  send(event) {
    this.onmessage({ data: JSON.stringify(event) });
  }
  drop() {
    this.onerror();
  }
}

const settle = () => new Promise((resolve) => setImmediate(resolve));
const answers = (...replies) => {
  const asked = [];
  const fetch = async (url) => {
    asked.push(url);
    const [status, data] = replies.length > 1 ? replies.shift() : replies[0];
    if (status === 0) throw new TypeError("Failed to fetch");
    return { status, json: async () => data };
  };
  return { fetch, asked };
};

function follow(deps = {}) {
  FakeSource.opened = [];
  const seen = { events: [], ends: [], connection: [] };
  const handle = followRun(
    "abc",
    {
      onEvent: (e) => seen.events.push(e.stage),
      onEnd: (e) => seen.ends.push(e),
      onConnection: (s) => seen.connection.push(s),
    },
    { EventSource: FakeSource, wait: async () => {}, pollMs: 0, ...deps },
  );
  return { seen, handle };
}

test("a stream that drops after the first event is reopened from the next event", async () => {
  const { seen } = follow();
  const first = FakeSource.opened[0];
  assert.equal(first.url, "/api/runs/abc/events?since=0");
  first.send({ stage: "fetch", status: "started" });
  first.drop();
  assert.ok(first.closed);
  assert.deepEqual(seen.connection, ["lost"]);
  assert.deepEqual(seen.ends, []); // not a failed run
  await settle();
  const second = FakeSource.opened[1];
  assert.equal(second.url, "/api/runs/abc/events?since=1");
  second.onopen();
  second.send({ stage: "pack", status: "done" });
  second.send({ stage: "run", status: "done" });
  assert.deepEqual(seen.connection, ["lost", "restored"]);
  assert.deepEqual(seen.events, ["fetch", "pack"]);
  assert.equal(seen.ends.length, 1);
  assert.equal(seen.ends[0].status, "done");
});

test("when reconnecting fails, the result is asked for and 'still running' is not a failure", async () => {
  const server = answers([0, {}], [200, { analyzed: true, company: "Coca Cola Co" }]);
  const { seen } = follow({ reconnectDelays: [], fetch: server.fetch });
  FakeSource.opened[0].drop();
  await settle();
  await settle();
  assert.deepEqual(server.asked, ["/api/runs/abc/result", "/api/runs/abc/result"]);
  assert.equal(seen.ends.length, 1);
  assert.equal(seen.ends[0].status, "done");
  assert.equal(seen.ends[0].result.company, "Coca Cola Co");
});

test("a 409 from the result means the run goes on: the stream is followed again", async () => {
  const server = answers([409, { detail: "The analysis is still running." }]);
  const { seen } = follow({ reconnectDelays: [], fetch: server.fetch });
  FakeSource.opened[0].drop();
  await settle();
  assert.equal(FakeSource.opened.length, 2);
  assert.deepEqual(seen.ends, []);
  FakeSource.opened[1].send({ stage: "run", status: "done" });
  assert.equal(seen.ends[0].status, "done");
});

test("a run the server no longer knows ends with that reason", async () => {
  const server = answers([404, {}]);
  const { seen } = follow({ reconnectDelays: [], fetch: server.fetch });
  FakeSource.opened[0].drop();
  await settle();
  assert.equal(seen.ends[0].status, "failed");
  assert.equal(seen.ends[0].text, FORGOTTEN);
});

test("after giving up, 'Check again' asks once more", async () => {
  const server = answers([0, {}], [0, {}], [200, { analyzed: false, error: "SEC refused the request." }]);
  const { seen, handle } = follow({ reconnectDelays: [], fetch: server.fetch, pollLimit: 2 });
  FakeSource.opened[0].drop();
  for (let i = 0; i < 4; i += 1) await settle();
  assert.deepEqual(seen.connection, ["lost", "gave_up"]);
  assert.deepEqual(seen.ends, []);
  handle.retry();
  await settle();
  assert.equal(seen.ends[0].status, "failed");
  assert.equal(seen.ends[0].text, "SEC refused the request.");
});

test("the final event of the server ends the run, failure included", () => {
  const { seen } = follow();
  FakeSource.opened[0].send({ stage: "run", status: "failed", text: "No annual statements." });
  assert.equal(seen.ends[0].text, "No annual statements.");
  assert.ok(FakeSource.opened[0].closed);
});
