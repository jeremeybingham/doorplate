// The doorplate npm package in Node. Every address here is invented.
// From the repository root, after `npm run build:wasm` in crates/doorplate-js:
//   node examples/javascript/quickstart.mjs
// Installed from npm, change the import to: import { init } from "doorplate";
import { init } from "../../crates/doorplate-js/src/index.js";

const dp = await init(); // once; loads doorplate.wasm
console.log("parser version:", dp.version);

const r = dp.parse("123 N. Main St #4, springfield il 62704");
console.log("key:   ", r.key);
console.log("usps:  ", r.usps.line1, "|", r.usps.last_line);
console.log("warns: ", r.warnings.join(", ") || "(none)");
// Spans are UTF-16 ranges, so slicing the input returns each component's text.
for (const s of r.spans) console.log(`  ${s.component}: ${JSON.stringify(r.input.slice(s.start, s.end))}`);

const f = dp.parseFields({ line1: "PO Box 12", city: "Reno", state: "NV", zip: "89501" });
console.log("fields key:", f.key);

const batch = dp.parseBatch(["1 Main St, Reno NV 89501", "", "RR 2 Box 14, Ocala FL 34470"]);
const keyCol = batch.columns.indexOf("key");
batch.rows.forEach((row, i) => console.log(`row ${i}:`, row ? row[keyCol] : null));
