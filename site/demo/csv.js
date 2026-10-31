// The "Parse a CSV file" section of the demo page (#335). The file is read in this browser tab,
// parsed in a Web Worker by the same WebAssembly as the box above, and the result is built in
// memory and offered as a download. Nothing is sent anywhere.
(function () {
  "use strict";
  var C = window.DoorplateCsv;
  var $ = function (id) { return document.getElementById(id); };
  var root = $("dp-csv");
  if (!root || !window.Worker || !window.WebAssembly || !C) return;

  var BATCH = 5000;
  var DEFAULT_COLUMNS = ["street_number", "street_dir_prefix", "street_name", "street_suffix", "street_dir_suffix",
    "unit_type", "unit_number", "city", "state", "zip5", "zip4", "usps_line1", "usps_last_line", "key", "warnings", "unparsed"];
  var SLOTS = [["line1", "Line 1"], ["line2", "Line 2"], ["city", "City"], ["state", "State"], ["zip", "ZIP"]];

  var worker, columns = null, file = null, encoding = "utf-8", delimiter = ",", headers = [], hasHeader = true;
  var running = false, cancelled = false, downloadUrl = null;
  var pending = {}, nextId = 1;

  // Defense in depth: after this, the page may load only its own files. 'wasm-unsafe-eval' is needed:
  // without it the browser refuses to compile WebAssembly, and the one-address demo above stops working
  // (this was a bug in the first version; tools/docs/smoke_demo_csv.py now checks the box too). Added when this script runs,
  // so it limits what happens from here on (the worker and the download); the claim itself is checked
  // in the browser's network tab and by tools/docs/smoke_demo_csv.py.
  try {
    var meta = document.createElement("meta");
    meta.httpEquiv = "Content-Security-Policy";
    meta.content = "default-src 'self'; connect-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; worker-src 'self' blob:; form-action 'none'";
    document.head.appendChild(meta);
  } catch (e) { /* the claim does not rest on this */ }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function say(id, text, cls) {
    var e = $(id);
    e.textContent = text;
    e.className = "dp-note" + (cls ? " " + cls : "");
    e.hidden = !text;
  }
  function mb(n) { return n >= 1e6 ? (n / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1e3)) + " KB"; }

  // The worker.
  function startWorker() {
    worker = new Worker("csv-worker.js");
    worker.onmessage = function (e) {
      var m = e.data;
      if (m.type === "ready") {
        columns = m.columns;
        buildColumnChecks();
        root.classList.add("dp-csv-ready");
        say("dp-csv-status", "");
        $("dp-csv-file").disabled = false;
      } else if (m.type === "failed") {
        say("dp-csv-status", "The parser could not be loaded for this section.", "dp-csv-bad");
      } else if (m.type === "result" && pending[m.id]) {
        pending[m.id](m.rows);
        delete pending[m.id];
      }
    };
    worker.postMessage({ type: "init", wasmUrl: new URL("doorplate.wasm", location.href).href });
  }
  function run(mode, rows) {
    return new Promise(function (resolve) {
      var id = nextId++;
      pending[id] = resolve;
      worker.postMessage({ type: "batch", id: id, mode: mode, rows: rows });
    });
  }

  // Which columns doorplate adds.
  function buildColumnChecks() {
    var box = $("dp-csv-cols");
    box.textContent = "";
    columns.forEach(function (c) {
      var lab = el("label", "dp-csv-check");
      var cb = el("input");
      cb.type = "checkbox";
      cb.value = c;
      cb.checked = DEFAULT_COLUMNS.indexOf(c) >= 0;
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(" " + c));
      box.appendChild(lab);
    });
  }
  function chosenColumns() {
    var out = [];
    Array.prototype.forEach.call($("dp-csv-cols").querySelectorAll("input"), function (cb) { if (cb.checked) out.push(cb.value); });
    return out;
  }

  // Reading the file.
  function pickEncoding(bytes) {
    try { new TextDecoder("utf-8", { fatal: true }).decode(bytes, { stream: true }); return "utf-8"; }
    catch (e) { return "windows-1252"; }
  }
  function stripBom(s) { return s.charCodeAt(0) === 0xFEFF ? s.slice(1) : s; }

  function onFile() {
    var f = $("dp-csv-file").files[0];
    $("dp-csv-config").hidden = true;
    $("dp-csv-result").hidden = true;
    if (!f) return;
    file = f;
    var head = f.slice(0, 262144);
    head.arrayBuffer().then(function (buf) {
      var bytes = new Uint8Array(buf);
      encoding = pickEncoding(bytes);
      var text = stripBom(new TextDecoder(encoding).decode(bytes));
      delimiter = C.detectDelimiter(text);
      var r = new C.Reader(delimiter), rows = r.push(text);
      var last = r.end();
      if (last && f.size <= 262144) rows.push(last);
      rows = rows.filter(function (x) { return !(x.length === 1 && x[0] === ""); });
      if (!rows.length) { say("dp-csv-status", "That file has no rows.", "dp-csv-bad"); return; }
      showConfig(f, rows);
    });
  }

  function showConfig(f, rows) {
    var width = rows[0].length;
    hasHeader = true;
    $("dp-csv-header").checked = true;
    headers = rows[0].map(function (h) { return h; });
    $("dp-csv-config").hidden = false;
    var info = f.name + " · " + mb(f.size) + " · " + (encoding === "utf-8" ? "UTF-8" : "Latin-1 (Windows-1252)") +
      " · delimiter " + (delimiter === "\t" ? "tab" : "“" + delimiter + "”") + " · " + width + " columns";
    say("dp-csv-info", info);
    var warn = "";
    if (f.size > 100e6) warn = "This file is large: the browser keeps the whole result in memory, and a file this size may run out. If it does, use the command-line tool (doorplate parse-file) or the Python package.";
    say("dp-csv-big", warn, "dp-csv-warn");
    fillSelects(width, rows);
    renderPreview(rows);
    updateMode();
  }
  function colName(i) { return hasHeader && headers[i] !== undefined && headers[i] !== "" ? headers[i] : "Column " + (i + 1); }
  function fillSelects(width, rows) {
    var ids = ["dp-csv-addr"].concat(SLOTS.map(function (s) { return "dp-csv-" + s[0]; }));
    var names = [];
    for (var i = 0; i < width; i++) names.push(colName(i));
    ids.forEach(function (id) {
      var sel = $(id), keep = sel.value;
      sel.textContent = "";
      if (id !== "dp-csv-addr" && id !== "dp-csv-line1") { var none = el("option", null, "(none)"); none.value = ""; sel.appendChild(none); }
      names.forEach(function (n, i2) { var o = el("option", null, n); o.value = String(i2); sel.appendChild(o); });
      var key = id === "dp-csv-addr" ? "address" : id.replace("dp-csv-", "");
      var g = hasHeader ? C.guessColumn(names, C.GUESS[key]) : -1;
      sel.value = g >= 0 ? String(g) : (id === "dp-csv-addr" || id === "dp-csv-line1" ? "0" : "");
      if (keep && !hasHeader && sel.querySelector('option[value="' + keep + '"]')) sel.value = keep;
    });
    $("dp-csv-config").dataset.rows = JSON.stringify(rows.slice(0, 6));
  }
  function renderPreview(rows) {
    var t = $("dp-csv-preview"), shown = rows.slice(hasHeader ? 1 : 0, hasHeader ? 6 : 5);
    t.textContent = "";
    var tr = el("tr");
    for (var i = 0; i < rows[0].length; i++) tr.appendChild(el("th", null, colName(i)));
    t.appendChild(tr);
    shown.forEach(function (r) {
      var row = el("tr");
      for (var i2 = 0; i2 < rows[0].length; i2++) row.appendChild(el("td", null, r[i2] === undefined ? "" : r[i2]));
      t.appendChild(row);
    });
  }
  function mode() { return $("dp-csv-mode-fields").checked ? "fields" : "line"; }
  function updateMode() {
    var fields = mode() === "fields";
    $("dp-csv-one").hidden = fields;
    $("dp-csv-multi").hidden = !fields;
  }

  // Running.
  function mapping() {
    if (mode() === "line") return { mode: "line", idx: [parseInt($("dp-csv-addr").value, 10)] };
    return { mode: "fields", idx: SLOTS.map(function (s) { var v = $("dp-csv-" + s[0]).value; return v === "" ? -1 : parseInt(v, 10); }) };
  }
  function cellsFor(row, m) {
    if (m.mode === "line") return row[m.idx[0]] === undefined ? "" : row[m.idx[0]];
    return m.idx.map(function (i) { return i < 0 || row[i] === undefined || row[i] === "" ? null : row[i]; });
  }

  async function start() {
    if (running || !file) return;
    var added = chosenColumns();
    if (!added.length) { say("dp-csv-status", "Choose at least one column to add.", "dp-csv-bad"); return; }
    var m = mapping();
    var useGuard = $("dp-csv-guard").checked;
    var wantIdx = added.map(function (c) { return columns.indexOf(c); });
    running = true; cancelled = false;
    $("dp-csv-go").hidden = true; $("dp-csv-cancel").hidden = false; $("dp-csv-result").hidden = true;
    say("dp-csv-status", "");
    var t0 = performance.now();
    var parts = [], total = 0, empty = 0, warned = 0, risky = 0, width = 0, pendingRows = [], first = true;
    var wcol = columns.indexOf("warnings");
    var reader = new C.Reader(delimiter);
    var decoder = new TextDecoder(encoding);
    var stream = file.stream().getReader();
    var read = 0, started = false;

    async function flush() {
      if (!pendingRows.length) return;
      var chunk = pendingRows; pendingRows = [];
      var results = await run(m.mode, chunk.map(function (r) { return cellsFor(r, m); }));
      if (cancelled) return;
      var lines = [];
      for (var i = 0; i < chunk.length; i++) {
        var res = results[i], row = chunk[i].slice(0, Math.max(width, chunk[i].length));
        while (row.length < width) row.push("");
        if (res === null) empty++;
        else if (wcol >= 0 && res[wcol] !== "") warned++;
        for (var k = 0; k < wantIdx.length; k++) {
          var v = res === null ? "" : res[wantIdx[k]];
          row.push(useGuard ? C.guard(v) : v);
        }
        lines.push(C.formatRow(row, delimiter));
      }
      parts.push(lines.join(""));
      total += chunk.length;
    }
    async function take(rows) {
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        if (r.length === 1 && r[0] === "") continue;
        if (first) {
          first = false;
          var head = r;
          if (!hasHeader) {
            head = r.map(function (_, i2) { return "Column " + (i2 + 1); });
          }
          headers = head;
          width = head.length;
          parts.push(C.formatRow(head.concat(added.map(function (c) { return "addr_" + c; })), delimiter));
          if (hasHeader) continue;
        }
        for (var j = 0; j < r.length; j++) if (C.looksLikeFormula(r[j])) { risky++; break; }
        pendingRows.push(r);
        if (pendingRows.length >= BATCH) {
          await flush();
          if (cancelled) return;
          say("dp-csv-status", total.toLocaleString() + " rows parsed (" + Math.min(99, Math.round(100 * read / file.size)) + "%)");
        }
      }
    }
    try {
      for (;;) {
        var step = await stream.read();
        if (cancelled) break;
        if (step.done) break;
        read += step.value.length;
        var text = decoder.decode(step.value, { stream: true });
        if (!started) { text = stripBom(text); started = true; }
        await take(reader.push(text));
        if (cancelled) break;
      }
      if (!cancelled) {
        var tail = decoder.decode();
        if (tail) await take(reader.push(tail));
        var lastRow = reader.end();
        if (lastRow) await take([lastRow]);
        await flush();
      }
    } catch (e) {
      cancelled = true;
      say("dp-csv-status", "Something went wrong while reading the file: " + (e && e.message ? e.message : "unknown error"), "dp-csv-bad");
    }
    running = false;
    $("dp-csv-go").hidden = false; $("dp-csv-cancel").hidden = true;
    if (cancelled) {
      if (!$("dp-csv-status").className.match("bad")) say("dp-csv-status", "Cancelled.");
      return;
    }
    finish(parts, total, empty, warned, risky, performance.now() - t0, added.length);
  }

  function finish(parts, total, empty, warned, risky, ms, nAdded) {
    var blob = new Blob(parts, { type: "text/csv;charset=utf-8" });
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    downloadUrl = URL.createObjectURL(blob);
    var a = $("dp-csv-download");
    a.href = downloadUrl;
    a.download = (file.name.replace(/\.[^.]*$/, "") || "addresses") + "-parsed.csv";
    a.textContent = "Download " + a.download + " (" + mb(blob.size) + ")";
    var lines = [total.toLocaleString() + " rows in " + (ms / 1000).toFixed(1) + " s, " + nAdded + " columns added (prefixed addr_)."];
    if (warned) lines.push(warned.toLocaleString() + " rows have a warning (the warnings column, if you kept it, says which).");
    if (empty) lines.push(empty.toLocaleString() + " rows had no address text; their new columns are empty.");
    if (risky) lines.push(risky.toLocaleString() + " rows hold text in your own columns that starts with =, @ or a sign and a letter; it is copied unchanged, and a spreadsheet may run it as a formula.");
    $("dp-csv-summary").textContent = "";
    lines.forEach(function (l) { $("dp-csv-summary").appendChild(el("p", "dp-note", l)); });
    $("dp-csv-result").hidden = false;
    say("dp-csv-status", "");
  }

  $("dp-csv-file").disabled = true;
  $("dp-csv-file").addEventListener("change", onFile);
  $("dp-csv-header").addEventListener("change", function () {
    hasHeader = $("dp-csv-header").checked;
    var rows = JSON.parse($("dp-csv-config").dataset.rows || "[]");
    if (rows.length) { fillSelects(rows[0].length, rows); renderPreview(rows); }
  });
  $("dp-csv-mode-line").addEventListener("change", updateMode);
  $("dp-csv-mode-fields").addEventListener("change", updateMode);
  $("dp-csv-go").addEventListener("click", start);
  $("dp-csv-cancel").addEventListener("click", function () { cancelled = true; });
  $("dp-csv-all").addEventListener("click", function () {
    Array.prototype.forEach.call($("dp-csv-cols").querySelectorAll("input"), function (cb) { cb.checked = true; });
  });
  $("dp-csv-default").addEventListener("click", function () {
    Array.prototype.forEach.call($("dp-csv-cols").querySelectorAll("input"), function (cb) { cb.checked = DEFAULT_COLUMNS.indexOf(cb.value) >= 0; });
  });
  startWorker();
})();
