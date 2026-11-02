// Runs the parser and the anonymizer for the "Parse a CSV file" section (#335, #434) off the page's thread. It loads
// doorplate.wasm from the page's own folder and talks only to the page that started it.
"use strict";
var wasm, enc = new TextEncoder(), dec = new TextDecoder();

function call(fn, obj) {
  var b = enc.encode(JSON.stringify(obj)), p = wasm.alloc(b.length);
  new Uint8Array(wasm.memory.buffer, p, b.length).set(b);
  var n = wasm[fn](p, b.length);
  wasm.dealloc(p, b.length);
  return JSON.parse(dec.decode(new Uint8Array(wasm.memory.buffer, wasm.result_ptr(), n)));
}
function batch(mode, rows) { return call("parse_batch", { mode: mode, rows: rows }); }

self.onmessage = function (e) {
  var m = e.data;
  if (m.type === "init") {
    fetch(m.wasmUrl).then(function (r) { return r.arrayBuffer(); })
      .then(function (bytes) { return WebAssembly.instantiate(bytes, {}); })
      .then(function (r) {
        wasm = r.instance.exports;
        self.postMessage({ type: "ready", columns: batch("line", []).columns });
      })
      .catch(function () { self.postMessage({ type: "failed" }); });
  } else if (m.type === "batch") {
    var out = batch(m.mode, m.rows);
    self.postMessage({ type: "result", id: m.id, rows: out.rows });
  } else if (m.type === "anon") {
    // [[text, faithful], ...] for the values sent, one seed for the whole file.
    var a = call("anonymize_batch", { seed: m.seed, rows: m.rows });
    self.postMessage({ type: "result", id: m.id, rows: a.rows });
  }
};
