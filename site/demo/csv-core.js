// The CSV parts of the "Parse a CSV file" section of the demo page (#335): a reader that takes
// text in chunks, a writer, delimiter detection and the formula guard. No DOM and no network, so
// Node can test it (tools/docs/test_demo_csv.py).
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.DoorplateCsv = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // A reader for RFC 4180 style CSV with any one-character delimiter: quoted fields, doubled quotes,
  // newlines inside quotes, CRLF or LF (a lone CR also ends a row). push(text) takes the next chunk
  // of text, wherever it was cut, and returns the rows that are complete; end() returns the last row
  // if the text did not end with a newline. A blank line is a row with one empty field (callers skip
  // the ones they do not want).
  function Reader(delimiter) {
    this.d = delimiter || ",";
    this.field = "";
    this.row = [];
    this.inQuotes = false;
    this.quoteSeen = false; // in quotes, the previous character was a quote
    this.skipLF = false; // the previous character ended a row with CR
    this.started = false; // any character of this row seen
  }
  Reader.prototype.push = function (text) {
    var out = [], d = this.d, i = 0, n = text.length, c;
    for (; i < n; i++) {
      c = text.charAt(i);
      if (this.skipLF) {
        this.skipLF = false;
        if (c === "\n") continue;
      }
      if (this.inQuotes) {
        if (this.quoteSeen) {
          this.quoteSeen = false;
          if (c === '"') { this.field += '"'; continue; }
          this.inQuotes = false; // the quote closed the field; c is handled below
        } else if (c === '"') {
          this.quoteSeen = true;
          continue;
        } else {
          this.field += c;
          continue;
        }
      }
      if (c === '"' && this.field === "" ) {
        this.inQuotes = true;
        this.started = true;
      } else if (c === d) {
        this.row.push(this.field);
        this.field = "";
        this.started = true;
      } else if (c === "\n" || c === "\r") {
        this.row.push(this.field);
        out.push(this.row);
        this.row = [];
        this.field = "";
        this.started = false;
        if (c === "\r") this.skipLF = true;
      } else {
        this.field += c;
        this.started = true;
      }
    }
    return out;
  };
  Reader.prototype.end = function () {
    // A quote that closed the field at the very end of the text.
    if (this.inQuotes && this.quoteSeen) { this.inQuotes = false; this.quoteSeen = false; }
    if (this.started || this.field !== "" || this.row.length) {
      this.row.push(this.field);
      var r = this.row;
      this.row = [];
      this.field = "";
      this.started = false;
      return r;
    }
    return null;
  };

  // The delimiter of a text sample: the one of , ; tab | that occurs most often in the first line
  // outside quotes (a comma if none does).
  function detectDelimiter(sample) {
    var counts = { ",": 0, ";": 0, "\t": 0, "|": 0 }, inQ = false, i, c;
    for (i = 0; i < sample.length; i++) {
      c = sample.charAt(i);
      if (c === '"') inQ = !inQ;
      else if (!inQ && (c === "\n" || c === "\r")) break;
      else if (!inQ && counts.hasOwnProperty(c)) counts[c]++;
    }
    var best = ",", k;
    for (k in counts) if (counts[k] > counts[best]) best = k;
    return best;
  }

  // One cell as it is written: quoted when it holds the delimiter, a quote, a newline or a CR.
  function quote(cell, delimiter) {
    var s = String(cell);
    if (s.indexOf('"') >= 0 || s.indexOf(delimiter) >= 0 || s.indexOf("\n") >= 0 || s.indexOf("\r") >= 0) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }
  function formatRow(cells, delimiter) {
    var d = delimiter || ",", parts = new Array(cells.length), i;
    for (i = 0; i < cells.length; i++) parts[i] = quote(cells[i], d);
    return parts.join(d) + "\n";
  }

  // Spreadsheets run a cell that starts with = + - @ (or a tab or CR) as a formula. A leading
  // apostrophe makes it text. Applied to the columns doorplate adds.
  var FORMULA = /^[=+\-@\t\r]/;
  function guard(cell) { return FORMULA.test(cell) ? "'" + cell : cell; }
  // Text in the user's own columns that a spreadsheet would run: not a plain number (-5, +3.2).
  var RISKY = /^([=@\t\r]|[+-][^0-9.\s])/;
  function looksLikeFormula(cell) { return RISKY.test(cell); }

  // Header guesses: the index of the first header that matches one of the patterns, or -1.
  function guessColumn(headers, patterns) {
    for (var p = 0; p < patterns.length; p++) {
      for (var i = 0; i < headers.length; i++) {
        if (patterns[p].test(headers[i].trim())) return i;
      }
    }
    return -1;
  }
  var GUESS = {
    address: [/^(full[ _-]?)?address$/i, /^(street[ _-]?)?address([ _-]?1)?$/i, /^addr(ess)?[ _-]?(line)?[ _-]?1?$/i, /^street$/i, /address/i],
    line1: [/^(street[ _-]?)?address([ _-]?(line)?[ _-]?1)?$/i, /^addr(ess)?[ _-]?(line)?[ _-]?1$/i, /^street$/i, /^line[ _-]?1$/i, /address/i],
    line2: [/^(street[ _-]?)?address([ _-]?(line)?[ _-]?2)$/i, /^addr(ess)?[ _-]?(line)?[ _-]?2$/i, /^line[ _-]?2$/i, /^(suite|unit|apt)/i],
    city: [/^city$/i, /^town$/i, /city/i],
    state: [/^state$/i, /^st$/i, /^province$/i, /state/i],
    zip: [/^zip([ _-]?code)?$/i, /^postal([ _-]?code)?$/i, /zip/i, /postal/i]
  };

  return {
    Reader: Reader, detectDelimiter: detectDelimiter, formatRow: formatRow, quote: quote,
    guard: guard, looksLikeFormula: looksLikeFormula, guessColumn: guessColumn, GUESS: GUESS
  };
});
