// Pure helpers of the review page (tools/review/page.html), kept apart so Node can test them
// (test_helpers.py). Plain ES5: the page loads this file as /helpers.js. No addresses live here.
(function (root) {
  // The row as one line, as the correction box starts: line 1, line 2, then the last line or
  // city, state and ZIP, joined with ", ". Mirrors oneline.py (a test compares the two).
  function oneLine(it) {
    var parts;
    if (it.last_line) parts = [it.line1, it.line2, it.last_line];
    else parts = [it.line1, it.line2, it.city, [it.state, it.zip].filter(Boolean).join(" ")];
    return parts.filter(Boolean).join(", ");
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

  // Pre-split fields from labels, to try what the library makes of a labeling: the street parts in the order
  // they were labeled go to line 1, the units to line 2, and the city, state and ZIP to their own fields.
  // `skipped` lists the labels that are not part of the delivery address (attention, building, not placed).
  var STREET = { StreetNumber: 1, StreetDirPrefix: 1, StreetName: 1, Highway: 1, StreetSuffix: 1, StreetDirSuffix: 1,
                 PoBox: 1, RuralRoute: 1, GeneralDelivery: 1, Military: 1, MilitaryPostOffice: 1 };
  var UNIT = { UnitType: 1, UnitNumber: 1, SecondUnitType: 1, SecondUnitNumber: 1 };
  function fieldsFromLabels(text, labels) {
    var line1 = [], line2 = [], city = [], state = [], zip5 = [], zip4 = [], skipped = [];
    (labels || []).forEach(function (l) {
      var w = text.slice(l.start, l.end).replace(/^[,\s]+|[,\s]+$/g, "");
      if (!w) return;
      if (STREET[l.component]) line1.push(w);
      else if (UNIT[l.component]) line2.push(w);
      else if (l.component === "City") city.push(w);
      else if (l.component === "State") state.push(w);
      else if (l.component === "Zip5") zip5.push(w);
      else if (l.component === "Zip4") zip4.push(w);
      else skipped.push(l.component);
    });
    var zip = zip5.join(" ") + (zip4.length ? "-" + zip4.join(" ") : "");
    var f = { line1: line1.join(" "), line2: line2.join(" "), city: city.join(" "), state: state.join(" "), zip: zip };
    Object.keys(f).forEach(function (k) { if (!f[k]) delete f[k]; });
    return { fields: f, skipped: skipped };
  }

  var api = { fieldsFromLabels: fieldsFromLabels, oneLine: oneLine, unchanged: unchanged, tokens: tokens,
              labelsFromSpans: labelsFromSpans, runs: runs };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReviewHelpers = api;
})(this);
