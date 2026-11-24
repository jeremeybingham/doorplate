// Compiled by `npm run types` (tsc --noEmit): the declared types must accept normal use of the package.
import { init, type ParseResult } from "../src/index.js";

const dp = await init();
const r: ParseResult = dp.parse("123 N Main St, Austin TX 78701");
if (!("error" in r)) {
  const key: string = r.key;
  const first = r.spans[0];
  const text: string = r.input.slice(first.start, first.end);
  void [key, text];
}
const b = dp.parseBatch(["1 Main St, Reno NV 89501"]);
const rows: (string[] | null)[] = b.rows;
dp.parseBatch([["1 Main St", null, "Reno", "NV", "89501"]], "fields");
dp.parseFields({ line1: "1 Main St", zip: "89501" });
void rows;
