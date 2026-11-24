# Using doorplate from JavaScript

The `doorplate` npm package is the Rust parser compiled to WebAssembly (`crates/doorplate-wasm`, the same file
the [live demo](https://jeremeybingham.github.io/doorplate/demo/) runs) with a small loader around it
(`crates/doorplate-js`). It is not published to npm yet (#878); until then, build it from the repository.

## Build and use

```sh
cd crates/doorplate-js
npm install          # the one dev dependency is TypeScript, for the type check
npm run build:wasm   # cargo build -p doorplate-wasm ... and copy the .wasm next to the package
npm test             # node --test, TypeScript check with `npm run types`
```

```js
import { init } from "doorplate";
const dp = await init();                       // once
const r = dp.parse("123 N Main St Apt 4, Springfield IL 62704");
```

- `parse(text)` returns the record `doorplate parse` prints (components, `warnings`, `key`, `usps`, `reso`,
  `place`, `provenance`) plus `spans`, the range of each component in UTF-16 units, so `text.slice(start, end)`
  works in JavaScript. An empty string returns `{ input, error }` rather than throwing.
- `parseFields({ line1, line2, city, state, zip })` is `Parser::parse_fields`; spans say which field they index.
- `parseBatch(rows, mode)` takes one-line strings (`"line"`) or `[line1, line2, city, state, zip]` arrays
  (`"fields"`) and returns `{ columns, rows }`, the columns of `doorplate parse-file`; a row with no address text
  is `null`. Large inputs are split into 10,000-row calls inside the package (one 100,000-row call is several
  times slower per row).
- `version` is the parser's version.

## Loading the wasm

`init()` reads the packaged `doorplate.wasm`: with `fs` in Node, and through `fetch(new URL("../doorplate.wasm",
import.meta.url))` in a browser or bundler (checked with Vite). Pass your own source for anything else:
`init(bytes)`, `init(webAssemblyModule)`, `init(url)` or `init(fetch(url))`.

## Size, speed, privacy

2.0 MB packed, 5.5 MB unpacked, 1.5 MB brotli; init about 25 ms; one `parse` about 60 µs, `parseBatch` about
26 µs a row (Node 20, 2026-11-24, `docs/speed-and-size.md` has the native figures). Nothing is uploaded and the
package loads no third-party script; its only network use is fetching its own `.wasm` in a browser.

## Not in this package yet

The release workflow and npm publish, a CommonJS build, Python-parity helpers (key helpers, custom layers,
`anonymize`) and a recipe for edge runtimes. They are follow-ups on #878.
