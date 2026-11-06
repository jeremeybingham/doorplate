// Parses a JSON file of [line1, line2, city, state, zip] rows with doorplate.wasm (parse_batch, fields mode, as the demo
// page's CSV section does) and writes one JSON array of the 30 output columns per line (null: no result). Counts only
// on stdout. Used by tools/compare/phase_g_check.py (#567): node wasm_batch.mjs DOORPLATE.wasm ROWS.json OUT.jsonl
import { readFileSync, writeFileSync, openSync, writeSync, closeSync } from "node:fs";

const [wasmPath, rowsPath, outPath] = process.argv.slice(2);
const { instance } = await WebAssembly.instantiate(readFileSync(wasmPath), {});
const wasm = instance.exports;
const enc = new TextEncoder();
const dec = new TextDecoder();

function call(fn, obj) {
  const b = enc.encode(JSON.stringify(obj));
  const p = wasm.alloc(b.length);
  new Uint8Array(wasm.memory.buffer, p, b.length).set(b);
  const n = wasm[fn](p, b.length);
  wasm.dealloc(p, b.length);
  return JSON.parse(dec.decode(new Uint8Array(wasm.memory.buffer, wasm.result_ptr(), n)));
}

const rows = JSON.parse(readFileSync(rowsPath, "utf8"));
const fd = openSync(outPath, "w");
const STEP = 20000;
let n = 0;
for (let i = 0; i < rows.length; i += STEP) {
  const out = call("parse_batch", { mode: "fields", rows: rows.slice(i, i + STEP) });
  if (out.error) throw new Error("wasm error");
  writeSync(fd, out.rows.map((r) => JSON.stringify(r)).join("\n") + "\n");
  n += out.rows.length;
}
closeSync(fd);
console.log(`wasm parsed ${n} rows`);
