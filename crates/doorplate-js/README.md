# doorplate (JavaScript)

Parse US addresses into components, a stable match key and USPS-style lines. The Rust parser compiled to
WebAssembly: it runs in Node and in the browser, with no dependencies and no network access. In a browser page
the addresses never leave the visitor's machine.

> **Beta, not yet published to npm.** The package is built from the same wasm as the
> [live demo](https://jeremeybingham.github.io/doorplate/demo/) and checked against the native build.

```js
import { init } from "doorplate";

const dp = await init(); // once; loads doorplate.wasm
const r = dp.parse("123 N Main St Apt 4, Springfield IL 62704");
r.key;        // "k6:S|123|N|MAIN|ST||IL|62704"
r.usps.line1; // "123 N MAIN ST APT 4"
r.spans;      // component ranges in UTF-16 units: text.slice(start, end)

dp.parseFields({ line1: "PO Box 12", city: "Reno", state: "NV", zip: "89501" });
dp.parseBatch(["1 Main St, Reno NV 89501", "..."]); // { columns, rows } like `doorplate parse-file`
```

`init()` takes an optional source (bytes, a `WebAssembly.Module`, a URL or a `Response`) for runtimes that cannot
read a sibling file, such as Cloudflare Workers. Node 18 or newer; ES modules only. Bundlers (Vite, webpack 5,
Next) pick up `doorplate.wasm` through `new URL(..., import.meta.url)`.

**Size and speed:** the package is 2.0 MB packed (5.5 MB unpacked, 1.5 MB with brotli), mostly place and street
tables. In Node, init takes about 25 ms, one `parse` about 60 µs, and `parseBatch` about 26 µs a row.

Guide: [JavaScript](https://doorplate.readthedocs.io/en/latest/javascript/). The records, the key and the
warning codes are the same as the command line and Python.

## Disclaimer

doorplate is provided "as is", without warranty of any kind, under the [MIT](https://github.com/jeremeybingham/doorplate/blob/main/LICENSE-MIT) or
[Apache-2.0](https://github.com/jeremeybingham/doorplate/blob/main/LICENSE-APACHE) license at your option; the license text is what governs. In plain
terms: **use it at your own risk.** Nothing here guarantees that a parse, a warning, a match key
or a figure is correct, complete or fit for your purpose. Accuracy and speed numbers are
measurements on particular datasets, not promises for yours. doorplate parses and formats
addresses; it does **not validate** that an address exists or can receive mail, and Pub 28
formatting is not certified validation. Check its output before you rely on it for anything with
legal, financial, safety or delivery consequences.

doorplate is an independent project. It is not affiliated with, endorsed by or certified by the
US Postal Service, RESO, DataMade (the authors of usaddress) or any data source it cites; those
names are used only to say what the output follows or is compared with.
