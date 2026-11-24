// doorplate for JavaScript: the Rust parser compiled to WebAssembly (crates/doorplate-wasm), wrapped in a
// small loader. No dependencies, no network access besides loading doorplate.wasm itself.
//
//   import { init } from "doorplate";
//   const dp = await init();
//   dp.parse("123 N Main St Apt 4, Springfield IL 62704").key;

const encoder = new TextEncoder();
const decoder = new TextDecoder();

// Rows per call to the wasm batch export. One call with 100,000 rows is several times slower per row than
// ten with 10,000 (one huge JSON string in and out), so `parseBatch` splits large inputs.
const BATCH_CHUNK = 10000;

async function readSource(source) {
  if (source === undefined) source = new URL("../doorplate.wasm", import.meta.url);
  source = await source;
  if (source instanceof WebAssembly.Module) return source;
  if (source instanceof URL || typeof source === "string") {
    const url = new URL(source, import.meta.url);
    if (url.protocol === "file:") {
      const { readFile } = await import("node:fs/promises");
      return WebAssembly.compile(await readFile(url));
    }
    source = await fetch(url);
  }
  if (typeof Response !== "undefined" && source instanceof Response) {
    if (!source.ok) throw new Error(`doorplate: could not load the wasm file (HTTP ${source.status})`);
    const type = source.headers.get("content-type") || "";
    if (type.startsWith("application/wasm") && WebAssembly.compileStreaming) {
      return WebAssembly.compileStreaming(source);
    }
    return WebAssembly.compile(await source.arrayBuffer());
  }
  return WebAssembly.compile(source); // ArrayBuffer or typed array
}

/**
 * Load the parser. Call once and keep the result.
 * `source` is optional: the packaged doorplate.wasm is loaded by default. It can also be the bytes, a
 * `WebAssembly.Module`, a URL, or a `Response` (or a promise of one), for runtimes that cannot read a
 * sibling file.
 */
export async function init(source) {
  const module = await readSource(source);
  let wasm = (await WebAssembly.instantiate(module, {})).exports;

  // One call: copy the input in, run, copy the result out. Memory is read fresh after the call because the
  // buffer is replaced when the memory grows; the result buffer is reused by the next call, so it is
  // decoded before returning.
  function call(fn, text) {
    const bytes = encoder.encode(text);
    const ptr = wasm.alloc(bytes.length);
    let out;
    try {
      new Uint8Array(wasm.memory.buffer, ptr, bytes.length).set(bytes);
      const n = wasm[fn](ptr, bytes.length);
      out = decoder.decode(new Uint8Array(wasm.memory.buffer, wasm.result_ptr(), n));
    } catch (e) {
      if (e instanceof WebAssembly.RuntimeError) {
        // A trap leaves the instance unusable: start a fresh one and report.
        WebAssembly.instantiate(module, {}).then((r) => (wasm = r.exports));
        throw new Error("doorplate: the parser failed on this input (WebAssembly trap)", { cause: e });
      }
      throw e;
    } finally {
      try {
        wasm.dealloc(ptr, bytes.length);
      } catch {
        /* the instance is being replaced */
      }
    }
    return JSON.parse(out);
  }

  const columns = call("parse_batch", JSON.stringify({ mode: "line", rows: [] })).columns;

  return {
    /** The parser's version, e.g. "0.7.2". */
    version: call("parse", "1 A St, Reno NV 89501").provenance.library_version,
    /** Parse one address line. The record has `error` (and no `components`) when the input is empty. */
    parse: (address) => call("parse", String(address)),
    /** Parse separate fields: `{ line1, line2, city, state, zip }`, any of them missing or null. */
    parseFields: (fields) => call("parse_fields", JSON.stringify(fields)),
    /**
     * Parse many one-line addresses (`mode: "line"`, strings) or field rows (`mode: "fields"`, arrays
     * `[line1, line2, city, state, zip]`). Returns `{ columns, rows }`: the columns of `doorplate parse-file`,
     * one array of strings per row, `null` for a row with no address text.
     */
    parseBatch(rows, mode = "line") {
      const out = [];
      for (let i = 0; i < rows.length || i === 0; i += BATCH_CHUNK) {
        const r = call("parse_batch", JSON.stringify({ mode, rows: rows.slice(i, i + BATCH_CHUNK) }));
        if (r.error) throw new Error(`doorplate: ${r.error}`);
        for (const row of r.rows) out.push(row);
      }
      return { columns, rows: out };
    },
  };
}
