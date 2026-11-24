import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { init } from "../src/index.js";

const fixtures = JSON.parse(readFileSync(new URL("./fixtures.json", import.meta.url), "utf8"));
const dp = await init();

test("every record equals the native `doorplate parse` record (spans aside)", () => {
  for (const { input, record } of fixtures.records) {
    const { spans, ...rest } = dp.parse(input);
    assert.ok(Array.isArray(spans), "spans present");
    assert.deepEqual(rest, record, `record for ${JSON.stringify(input.slice(0, 40))}`);
  }
});

test("spans slice the JS string, with emoji and combining marks", () => {
  for (const input of ["77 Emoji Rd 😀, Austin TX 78701", "12 Café Ünïcode St, Miami FL 33101", "12 Café St, Miami FL 33101"]) {
    const r = dp.parse(input);
    assert.ok(!("error" in r));
    const num = r.spans.find((s) => s.component === "StreetNumber");
    assert.equal(input.slice(num.start, num.end), r.components.street_number);
    const state = r.spans.find((s) => s.component === "State");
    assert.equal(input.slice(state.start, state.end).toUpperCase(), r.components.state);
    const zip = r.spans.find((s) => s.component === "Zip5");
    assert.equal(input.slice(zip.start, zip.end), r.components.zip5);
  }
});

test("an empty string is an error record, not a throw", () => {
  for (const text of fixtures.errors) {
    const r = dp.parse(text);
    assert.equal(typeof r.error, "string");
  }
});

test("parseFields agrees with the same address as one line on the key", () => {
  const a = dp.parseFields({ line1: "123 N Main St Apt 4", city: "Springfield", state: "IL", zip: "62704" });
  assert.equal(a.key, dp.parse("123 N Main St Apt 4, Springfield IL 62704").key);
});

test("parseBatch rows match parse, keys included, across chunk boundaries", () => {
  const rows = Array.from({ length: 25000 }, (_, i) => `${i + 1} Oak Ave, Austin TX 787${String(i % 100).padStart(2, "0")}`);
  rows[7] = "";
  const b = dp.parseBatch(rows);
  assert.equal(b.rows.length, rows.length);
  assert.equal(b.rows[7], null);
  const k = b.columns.indexOf("key");
  for (const i of [0, 9999, 10000, 24999]) assert.equal(b.rows[i][k], dp.parse(rows[i]).key);
  assert.deepEqual(dp.parseBatch([]).rows, []);
});

test("odd input does not break the instance", () => {
  for (const text of ["\ud800 lone surrogate", "NUL\u0000byte 1 Main St", "é".repeat(500000), "   "]) {
    dp.parse(text);
  }
  assert.equal(dp.parse("1 Main St, Reno NV 89501").components.state, "NV");
});

test("two instances in one process are independent; version matches package.json", async () => {
  const other = await init();
  assert.equal(other.parse("1 Main St, Reno NV 89501").key, dp.parse("1 Main St, Reno NV 89501").key);
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
  assert.equal(dp.version, pkg.version);
});

test("init accepts bytes and a compiled module", async () => {
  const bytes = readFileSync(new URL("../doorplate.wasm", import.meta.url));
  const a = await init(bytes);
  const b = await init(await WebAssembly.compile(bytes));
  assert.equal(a.parse("1 Main St, Reno NV 89501").key, b.parse("1 Main St, Reno NV 89501").key);
});
