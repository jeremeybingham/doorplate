export type Source = ArrayBuffer | ArrayBufferView | WebAssembly.Module | URL | string | Response | Promise<Response>;

/** A component's range in the text it indexes, in UTF-16 units: `text.slice(start, end)` is the component. */
export interface Span {
  /** Component name, e.g. "StreetName", "Zip5". */
  component: string;
  /** For `parseFields`, the field the range indexes ("line1", "line2", "city", "state", "zip"); otherwise null. */
  field: "line1" | "line2" | "city" | "state" | "zip" | null;
  start: number;
  end: number;
}

/** The record `doorplate parse` prints, plus `spans`. Fields not listed here may be added in later versions. */
export interface ParsedRecord {
  input: string;
  components: Record<string, string>;
  warnings: string[];
  unparsed: string | null;
  key: string;
  key_unit: string;
  slug: string;
  usps: { line1: string | null; line2: string | null; last_line: string | null };
  reso: Record<string, string>;
  place: Record<string, string> | null;
  provenance: { library_version: string; custom_layer: string | null };
  spans: Span[];
}

/** What `parse` returns for input it cannot parse (an empty string). */
export interface ParseErrorRecord {
  input: string;
  error: string;
}

export type ParseResult = ParsedRecord | ParseErrorRecord;

export interface Fields {
  line1?: string | null;
  line2?: string | null;
  city?: string | null;
  state?: string | null;
  zip?: string | null;
}

export interface BatchResult {
  /** The columns of `doorplate parse-file` (street_number, ..., key, key_unit, slug, warnings, unparsed). */
  columns: string[];
  /** One array of strings per input row, in `columns` order; null for a row with no address text. */
  rows: (string[] | null)[];
}

export interface Doorplate {
  readonly version: string;
  parse(address: string): ParseResult;
  parseFields(fields: Fields): ParseResult;
  parseBatch(rows: string[], mode?: "line"): BatchResult;
  parseBatch(rows: (string | null)[][], mode: "fields"): BatchResult;
}

export function init(source?: Source): Promise<Doorplate>;
