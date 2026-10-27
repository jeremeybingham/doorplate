// Pure helpers of the review page (tools/review/page.html), kept apart so Node can test them
// (test_helpers.py). Plain ES5: the page loads this file as /helpers.js. No addresses live here.
(function (root) {
  var CARE = /^(%|C\/O\b|C\\O\b|CO\b|ATTN\b|ATT\b|ATTENTION\b)/i;

  function words(s) { return String(s || "").trim().split(/\s+/).filter(Boolean); }

  // The row as one line, as the correction box starts: line 1, line 2, then the last line or
  // city, state and ZIP, joined with ", ". Mirrors oneline.py (a test compares the two).
  function oneLine(it) {
    var parts;
    if (it.last_line) parts = [it.line1, it.line2, it.last_line];
    else parts = [it.line1, it.line2, it.city, [it.state, it.zip].filter(Boolean).join(" ")];
    return parts.filter(Boolean).join(", ");
  }

  // The row with its first `n` words of line 1 moved to the care-of line: `% WORDS` after line 1
  // when there is no care-of line, appended to line 2 when line 2 is one (starts with %, C/O, ATTN),
  // and a new `% WORDS` part before line 2 when line 2 is something else (a unit). `n` is clamped
  // so line 1 keeps at least one word. Returns the one-line string, ready for the correction box.
  function moveWords(it, n) {
    var w = words(it.line1);
    n = Math.max(0, Math.min(n, w.length - 1));
    if (n === 0) return oneLine(it);
    var moved = w.slice(0, n).join(" "), copy = {};
    Object.keys(it).forEach(function (k) { copy[k] = it[k]; });
    copy.line1 = w.slice(n).join(" ");
    var line2 = (it.line2 || "").trim();
    if (!line2) copy.line2 = "% " + moved;
    else if (CARE.test(line2)) copy.line2 = line2 + " " + moved;
    else {
      // line 2 is a unit or a place name: the care-of part goes between line 1 and it
      copy.line1 = copy.line1 + ", % " + moved;
    }
    return oneLine(copy);
  }

  // Is the correction box unchanged, so the answer is really "the parse is right"?
  function unchanged(it, text) {
    return String(text).replace(/\s+/g, " ").trim() === oneLine(it).replace(/\s+/g, " ").trim();
  }

  // Tokens of a string for span labeling: [{start, end, text}], split on whitespace; a comma stays
  // on its word so a span never splits "ST,".
  function tokens(text) {
    var out = [], re = /\S+/g, m;
    while ((m = re.exec(text))) out.push({ start: m.index, end: m.index + m[0].length, text: m[0] });
    return out;
  }

  // Turn parser spans ({start, end, component}) into one label per token run, so the labeling
  // starts from what the parser did and only the wrong parts need fixing. A token covered by no
  // span gets `Unparsed`.
  function labelsFromSpans(text, spans) {
    return tokens(text).map(function (t) {
      var hit = null;
      (spans || []).forEach(function (s) { if (!hit && s.start < t.end && t.start < s.end) hit = s.component; });
      return { start: t.start, end: t.end, component: hit || "Unparsed" };
    });
  }

  // Merge neighbouring tokens with the same component into runs: [{start, end, component}].
  function runs(labels) {
    var out = [];
    labels.forEach(function (l) {
      var last = out[out.length - 1];
      if (last && last.component === l.component) last.end = l.end;
      else out.push({ start: l.start, end: l.end, component: l.component });
    });
    return out;
  }

  var api = { oneLine: oneLine, moveWords: moveWords, unchanged: unchanged, tokens: tokens,
              labelsFromSpans: labelsFromSpans, runs: runs };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReviewHelpers = api;
})(this);
