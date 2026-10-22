// Every script of the page parses as an ES module, as the browser loads it. A syntax error in
// app.js leaves the page blank with no test of its pure modules failing (found 2026-10-22).
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

const STATIC = new URL("../../web/static/", import.meta.url);

for (const name of readdirSync(STATIC).filter((file) => file.endsWith(".js"))) {
  test(`${name} parses as a module`, () => {
    const source = readFileSync(new URL(name, STATIC), "utf8");
    const result = spawnSync(process.execPath, ["--check", "--input-type=module"], { input: source, encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
  });
}
