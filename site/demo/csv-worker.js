// Runs the parser for the "Parse a CSV file" section (#335) off the page's thread. It loads
// doorplate.wasm from the page's own folder and talks only to the page that started it.
"use strict";
var wasm, enc = new TextEncoder(), dec = new TextDecoder();

function batch(mode, rows) {
  var b = enc.encode(JSON.stringify({ mode: mode, rows: rows })), p = wasm.alloc(b.length);
  new Uint8Array(wasm.memory.buffer, p, b.length).set(b);
  var n = wasm.parse_batch(p, b.length);
  wasm.dealloc(p, b.length);
  return JSON.parse(dec.decode(new Uint8Array(wasm.memory.buffer, wasm.result_ptr(), n)));
}

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
  }
};
