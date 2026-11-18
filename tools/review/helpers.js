// Pure helpers of the review page (tools/review/page.html), kept apart so Node can test them
// (test_helpers.py). Plain ES5: the page loads this file as /helpers.js. No addresses live here.
(function (root) {
  // The row as one line, as the labeler shows it: line 1, line 2, then the last line or
  // city, state and ZIP, joined with ", ". Mirrors oneline.py (a test compares the two).
  function oneLine(it) {
    var parts;
    if (it.last_line) parts = [it.line1, it.line2, it.last_line];
    else parts = [it.line1, it.line2, it.city, [it.state, it.zip].filter(Boolean).join(" ")];
    return parts.filter(Boolean).join(", ");
  }

  // [start, end) of each space-separated word; a trailing , or ; is left out, and a lone comma is no word.
  function words(text) {
    var out = [], re = /\S+/g, m;
    while ((m = re.exec(text))) {
      var e = m.index + m[0].length;
      while (e > m.index && ",;".indexOf(text[e - 1]) >= 0) e--;
      if (e > m.index) out.push([m.index, e]);
    }
    return out;
  }

  function byStart(a, b) { return a.start - b.start; }

  // Labels on [s, e) removed, keeping the parts of labels that stick out of it.
  function clearRange(labels, s, e) {
    var out = [];
    labels.forEach(function (l) {
      if (l.end <= s || l.start >= e) out.push(l);
      else {
        if (l.start < s) out.push({ start: l.start, end: s, component: l.component });
        if (l.end > e) out.push({ start: e, end: l.end, component: l.component });
      }
    });
    return out.sort(byStart);
  }

  // [s, e) gets `component`; whatever was there before is cut away.
  function setLabel(labels, s, e, component) {
    var out = clearRange(labels, s, e);
    out.push({ start: s, end: e, component: component });
    return out.sort(byStart);
  }

  // The labeling starts from what the parser did: its spans (trimmed of spaces and edge commas, overlaps dropped),
  // and every stretch of a word it left out as `Unparsed`. Spans may cut inside a word (a glued `12B`).
  function initialLabels(text, spans) {
    var out = [], at = 0;
    (spans || []).slice().sort(function (a, b) { return a.start - b.start || b.end - a.end; }).forEach(function (sp) {
      var s = Math.max(sp.start, at), e = Math.min(sp.end, text.length);
      while (s < e && /[\s,;]/.test(text[s])) s++;
      while (e > s && /[\s,;]/.test(text[e - 1])) e--;
      if (s >= e) return;
      out.push({ start: s, end: e, component: sp.component }); at = e;
    });
    var covered = new Array(text.length);
    out.forEach(function (l) { for (var i = l.start; i < l.end; i++) covered[i] = true; });
    words(text).forEach(function (w) {
      for (var i = w[0]; i < w[1];) {
        if (covered[i]) { i++; continue; }
        var j = i; while (j < w[1] && !covered[j]) j++;
        out.push({ start: i, end: j, component: "Unparsed" }); i = j;
      }
    });
    return out.sort(byStart);
  }

  // Neighbouring labels of one part with only spaces (or nothing) between them become one, as they are saved.
  function merged(text, labels) {
    var out = [];
    labels.slice().sort(byStart).forEach(function (l) {
      var last = out[out.length - 1];
      if (last && last.component === l.component && !text.slice(last.end, l.start).trim()) last.end = l.end;
      else out.push({ start: l.start, end: l.end, component: l.component });
    });
    return out;
  }

  // Do two labelings say the same thing (after merging)?
  function sameLabels(text, a, b) {
    return JSON.stringify(merged(text, a)) === JSON.stringify(merged(text, b));
  }

  // Pre-split fields from labels, to see what the library makes of a labeling: the street parts in the order
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

  var api = { fieldsFromLabels: fieldsFromLabels, oneLine: oneLine, words: words, clearRange: clearRange, setLabel: setLabel,
              initialLabels: initialLabels, merged: merged, sameLabels: sameLabels };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReviewHelpers = api;
})(this);
