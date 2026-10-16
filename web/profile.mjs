// warrant-pdf/0 in JavaScript: the second implementation of the profile.
// It mirrors warrant_pdf/*.py rule for rule. Every Python counter-vector also
// runs here and must give the same outcome (tests/test_counter_vectors.py).
// The reader's warrant is passed in as { verifyStore, recordId }; this module
// never re-implements canonical form, WarrantIDs, signatures or key state.

export const PROFILE = "warrant-pdf/0";
const MAX_BUNDLE = 8 * 1024 * 1024;
const MAX_ENTRIES = 2048;
const MAX_ISO_TS = 253402300799;
const EXPECTED_WARNING = "unadopted root";
const HEX64 = /^[0-9a-f]{64}$/;
const B64 = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;
const MARKER = "%WARRANT-PDF-BUNDLE/";
const MARKER_LINE = /%WARRANT-PDF-BUNDLE\/0 len=([0-9]{1,9}) sha256=([0-9a-f]{64})\n/y;
const TERMS_FIELDS = ["attachments", "clauses", "parties", "profile", "title"];
const LINES_PER_PAGE = 60;
const WIDTH = 92;

export class Refusal extends Error {
  constructor(code, detail) {
    super(`${code}: ${detail}`);
    this.code = code;
    this.detail = detail;
  }
}

const utf8 = new TextEncoder();
const strictUtf8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const isHex64 = (v) => typeof v === "string" && HEX64.test(v);
const sameKeys = (o, keys) => {
  const k = Object.keys(o).sort();
  return k.length === keys.length && k.every((x, i) => x === keys[i]);
};

export async function sha256hex(bytes) {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(d, (b) => b.toString(16).padStart(2, "0")).join("");
}

function latin1(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return s;
}

function fromLatin1(s) {
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

function concat(parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

const equalBytes = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

function parseJson(raw, code) {
  let text;
  try {
    text = strictUtf8.decode(raw);
  } catch (e) {
    throw new Refusal(code, `not UTF-8: ${e.message}`);
  }
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new Refusal(code, e.message);
  }
}

// Python's json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True).
function codePointCompare(a, b) {
  const x = Array.from(a, (c) => c.codePointAt(0));
  const y = Array.from(b, (c) => c.codePointAt(0));
  for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] - y[i];
  return x.length - y.length;
}

const SHORT = { '"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t", "\b": "\\b", "\f": "\\f" };

function pyString(s) {
  let out = '"';
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    const u = s.charCodeAt(i);
    if (SHORT[ch]) out += SHORT[ch];
    else if (u < 0x20 || u > 0x7e) out += "\\u" + u.toString(16).padStart(4, "0");
    else out += ch;
  }
  return out + '"';
}

export function pyJson(v) {
  if (v === null) return "null";
  if (v === true) return "true";
  if (v === false) return "false";
  if (typeof v === "number") {
    if (!Number.isInteger(v)) throw new Refusal("BUNDLE_MALFORMED", "non-integer number");
    return String(v);
  }
  if (typeof v === "string") return pyString(v);
  if (Array.isArray(v)) return "[" + v.map(pyJson).join(",") + "]";
  const keys = Object.keys(v).sort(codePointCompare);
  return "{" + keys.map((k) => pyString(k) + ":" + pyJson(v[k])).join(",") + "}";
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((x, i) => deepEqual(x, b[i]));
  if (isObject(a) && isObject(b)) {
    const ka = Object.keys(a);
    return ka.length === Object.keys(b).length && ka.every((k) => Object.hasOwn(b, k) && deepEqual(a[k], b[k]));
  }
  return false;
}

// --- bundle (ADR-0004) ------------------------------------------------------

export function encodeBundle(records, blobs) {
  const b64 = {};
  for (const [h, b] of Object.entries(blobs)) b64[h] = btoa(latin1(b));
  return utf8.encode(pyJson({ blobs: b64, bundle: PROFILE, records }));
}

export async function decodeBundle(raw) {
  if (raw.length > MAX_BUNDLE) throw new Refusal("BUNDLE_LIMIT", `bundle larger than ${MAX_BUNDLE} bytes`);
  const doc = parseJson(raw, "BUNDLE_MALFORMED");
  if (!isObject(doc) || !sameKeys(doc, ["blobs", "bundle", "records"]) || doc.bundle !== PROFILE) {
    throw new Refusal("BUNDLE_MALFORMED", "top-level fields");
  }
  const records = doc.records;
  if (!isObject(records) || !isObject(doc.blobs)) throw new Refusal("BUNDLE_MALFORMED", "records/blobs must be objects");
  if (Object.keys(records).length + Object.keys(doc.blobs).length > MAX_ENTRIES) {
    throw new Refusal("BUNDLE_LIMIT", `more than ${MAX_ENTRIES} entries`);
  }
  for (const [name, rec] of Object.entries(records)) {
    if (!isHex64(name) || !isObject(rec) || !sameKeys(rec, ["body", "sigs"])) {
      throw new Refusal("BUNDLE_MALFORMED", `record entry ${name.slice(0, 80)}`);
    }
  }
  const blobs = {};
  for (const [name, b64] of Object.entries(doc.blobs)) {
    if (!isHex64(name) || typeof b64 !== "string") throw new Refusal("BUNDLE_MALFORMED", `blob entry ${name.slice(0, 80)}`);
    if (!B64.test(b64)) throw new Refusal("BUNDLE_MALFORMED", `blob ${name}: invalid base64`);
    const data = fromLatin1(atob(b64));
    if ((await sha256hex(data)) !== name) throw new Refusal("NAME_MISMATCH", `blob ${name} does not hash to its name`);
    blobs[name] = data;
  }
  return { records, blobs };
}

export function embedObject(bundleBytes, digest) {
  return concat([utf8.encode(`%WARRANT-PDF-BUNDLE/0 len=${bundleBytes.length} sha256=${digest}\nstream\n`),
    bundleBytes, utf8.encode("\nendstream")]);
}

export async function extract(pdf) {
  const s = latin1(pdf);
  const starts = [];
  for (let i = s.indexOf(MARKER); i !== -1; i = s.indexOf(MARKER, i + MARKER.length)) {
    if (i === 0 || s[i - 1] === "\n" || s[i - 1] === "\r") starts.push(i);
  }
  if (starts.length === 0) throw new Refusal("BUNDLE_MISSING", "no bundle marker");
  if (starts.length !== 1) throw new Refusal("BUNDLE_AMBIGUOUS", `${starts.length} bundle markers`);
  MARKER_LINE.lastIndex = starts[0];
  const m = MARKER_LINE.exec(s);
  if (!m) throw new Refusal("BUNDLE_MALFORMED", "marker line");
  const length = parseInt(m[1], 10);
  const digest = m[2];
  if (length > MAX_BUNDLE) throw new Refusal("BUNDLE_LIMIT", `bundle larger than ${MAX_BUNDLE} bytes`);
  const pos = MARKER_LINE.lastIndex;
  if (s.slice(pos, pos + 7) !== "stream\n") throw new Refusal("BUNDLE_MALFORMED", "stream keyword");
  const data = pdf.subarray(pos + 7, pos + 7 + length);
  if (data.length !== length || s.slice(pos + 7 + length, pos + 17 + length) !== "\nendstream") {
    throw new Refusal("BUNDLE_MALFORMED", "stream length");
  }
  if ((await sha256hex(data)) !== digest) throw new Refusal("BUNDLE_DIGEST", "bundle bytes do not match the marker digest");
  return data;
}

// --- terms and profile rules (ADR-0002) -------------------------------------

export function parseTerms(raw) {
  const t = parseJson(raw, "TERMS_MALFORMED");
  if (!isObject(t) || !sameKeys(t, TERMS_FIELDS)) throw new Refusal("TERMS_MALFORMED", "fields");
  if (t.profile !== PROFILE) throw new Refusal("TERMS_MALFORMED", "unknown profile");
  if (typeof t.title !== "string" || !t.title) throw new Refusal("TERMS_MALFORMED", "title");
  if (!Array.isArray(t.clauses) || !t.clauses.every((c) => typeof c === "string")) throw new Refusal("TERMS_MALFORMED", "clauses");
  const p = t.parties;
  if (!Array.isArray(p) || !p.every((x) => typeof x === "string" && x) || new Set(p).size !== p.length) {
    throw new Refusal("TERMS_MALFORMED", "parties");
  }
  for (const a of Array.isArray(t.attachments) ? t.attachments : [null]) {
    if (!isObject(a) || !sameKeys(a, ["name", "sha256"]) || typeof a.name !== "string" || !isHex64(a.sha256)) {
      throw new Refusal("TERMS_MALFORMED", "attachments");
    }
  }
  return t;
}

export function arrange(records, blobs, profileHash) {
  const entries = Object.entries(records);
  const proposes = entries.filter(([, r]) => r.body.decision === "propose");
  if (proposes.length !== 1) throw new Refusal("PROFILE_PROPOSE", `${proposes.length} propose records; exactly one required`);
  const [pid, prop] = proposes[0];
  const body = prop.body;
  const ordered = entries.slice().sort(([wa, a], [wb, b]) =>
    ((a.body.ts ?? 0) - (b.body.ts ?? 0)) || (wa < wb ? -1 : wa > wb ? 1 : 0));
  const accepts = [];
  const others = [];
  for (const [w, r] of ordered) {
    if (w === pid) continue;
    (r.body.decision === "accept" ? accepts : others).push([w, r]);
  }
  if (others.length) throw new Refusal("PROFILE_FOREIGN_RECORD", `record ${others[0][0]} is neither the propose nor an accept`);
  for (const [w, r] of [[pid, prop], ...accepts]) {
    if (!deepEqual(r.body.under, [profileHash])) throw new Refusal("PROFILE_UNDER", `record ${w} is not filed under ${profileHash}`);
  }
  const termsHash = body.subject.hash;
  if (!Object.hasOwn(blobs, termsHash)) throw new Refusal("PROFILE_TERMS", "the terms blob named by the propose subject is not in the bundle");
  const terms = parseTerms(blobs[termsHash]);
  const evidence = new Set(body.evidence);
  if (![termsHash, ...terms.attachments.map((a) => a.sha256)].every((h) => evidence.has(h))) {
    throw new Refusal("PROFILE_EVIDENCE", "the propose evidence does not list the terms and every attachment");
  }
  for (const [w, r] of accepts) {
    const b = r.body;
    if (!deepEqual(b.prior, [pid])) throw new Refusal("PROFILE_PRIOR", `accept ${w} does not respond to exactly the propose`);
    if (!deepEqual(b.subject, body.subject)) throw new Refusal("PROFILE_SUBJECT", `accept ${w} names another subject`);
    if (b.actor.id === body.actor.id) throw new Refusal("PROFILE_SELF_ACCEPT", `accept ${w} is by the proposer`);
  }
  const signed = new Set([body.actor.id, ...accepts.map(([, r]) => r.body.actor.id)]);
  const missing = terms.parties.filter((p) => !signed.has(p));
  if (missing.length) throw new Refusal("PROFILE_PARTY_UNSIGNED", `named party ${missing[0]} has no record`);
  if (!accepts.length) throw new Refusal("PROFILE_NO_ACCEPT", "nobody accepted");
  return { terms, propose: [pid, prop], accepts };
}

// --- canonical text and rendering (ADR-0005) --------------------------------

export function iso(ts) {
  if (ts > MAX_ISO_TS) return `unix ${ts}`;
  return new Date(ts * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function canonicalText(terms, propose, accepts) {
  const lines = ["WARRANT-PDF/0 CONTRACT", "", `Title: ${terms.title}`, ""];
  const clauses = terms.clauses.map((c, i) => `${i + 1}. ${c}`);
  lines.push(...(clauses.length ? clauses : ["(no clauses)"]));
  lines.push("", "Named parties: " + (terms.parties.join(", ") || "(none named)"));
  lines.push("", "Attachments (SHA-256 of the exact bytes):");
  const att = terms.attachments.map((a) => `  ${a.name}  ${a.sha256}`);
  lines.push(...(att.length ? att : ["  (none)"]));
  lines.push("", "Signed records (warrant):");
  for (const [wid, rec] of [propose, ...accepts]) {
    const b = rec.body;
    lines.push(`  ${b.decision} by ${b.actor.id} at ${iso(b.ts)}`);
    lines.push(`    record ${wid}`);
    for (const s of rec.sigs) lines.push(`    key ${s.key}`);
  }
  lines.push("", "This page is a rendering. The signed content is the embedded",
    "warrant bundle; `python3 -m warrant_pdf verify FILE --trust YOURS.json`",
    "checks the signatures under your trust config and whether this page",
    "matches a fresh rendering of what was signed.");
  return lines;
}

function pdfText(line) {
  return Array.from(line, (c) => {
    const cp = c.codePointAt(0);
    return cp >= 32 && cp < 127 ? c : "?";
  }).join("").replaceAll("\\", "\\\\").replaceAll("(", "\\(").replaceAll(")", "\\)");
}

function wrap(lines) {
  const out = [];
  for (const line of lines) {
    let cps = Array.from(line);
    while (cps.length > WIDTH) {
      out.push(cps.slice(0, WIDTH).join(""));
      cps = Array.from("    ").concat(cps.slice(WIDTH));
    }
    out.push(cps.join(""));
  }
  return out;
}

export async function render(lines, bundleBytes) {
  const wrapped = wrap(lines);
  const pages = [];
  for (let i = 0; i < wrapped.length; i += LINES_PER_PAGE) pages.push(wrapped.slice(i, i + LINES_PER_PAGE));
  if (!pages.length) pages.push([]);
  const pageIds = pages.map((_, i) => 7 + 2 * i);
  const objs = new Map();
  const a = (s) => utf8.encode(s);
  objs.set(1, a("<< /Type /Catalog /Pages 2 0 R /Names << /EmbeddedFiles 4 0 R >> >>"));
  objs.set(2, a(`<< /Type /Pages /Count ${pages.length} /Kids [${pageIds.map((p) => `${p} 0 R`).join(" ")}] >>`));
  objs.set(3, a("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"));
  objs.set(4, a("<< /Names [(warrant-bundle.json) 5 0 R] >>"));
  objs.set(5, a("<< /Type /Filespec /F (warrant-bundle.json) /UF (warrant-bundle.json) /EF << /F 6 0 R >> >>"));
  objs.set(6, concat([a(`<< /Type /EmbeddedFile /Subtype /application#2Fjson /Length ${bundleBytes.length} >>\n`),
    embedObject(bundleBytes, await sha256hex(bundleBytes))]));
  pages.forEach((page, i) => {
    const pid = pageIds[i];
    const content = ["BT /F1 9 Tf 11 TL 40 800 Td", ...page.map((l) => `(${pdfText(l)}) '`), "ET"].join("\n");
    objs.set(pid, a(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents ${pid + 1} 0 R >>`));
    objs.set(pid + 1, a(`<< /Length ${content.length} >>\nstream\n${content}\nendstream`));
  });
  const parts = [new Uint8Array([...a("%PDF-1.7\n%"), 0xe2, 0xe3, 0xcf, 0xd3, 0x0a])];
  let size = parts[0].length;
  const offsets = new Map();
  for (const n of [...objs.keys()].sort((x, y) => x - y)) {
    offsets.set(n, size);
    const obj = concat([a(`${n} 0 obj\n`), objs.get(n), a("\nendobj\n")]);
    parts.push(obj);
    size += obj.length;
  }
  const xref = size;
  const count = Math.max(...objs.keys()) + 1;
  let tail = `xref\n0 ${count}\n0000000000 65535 f \n`;
  for (let n = 1; n < count; n++) tail += `${String(offsets.get(n)).padStart(10, "0")} 00000 n \n`;
  tail += `trailer\n<< /Size ${count} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  parts.push(a(tail));
  return concat(parts);
}

// --- verify (the order of verify.py) ----------------------------------------

export async function verify(pdf, trust, warrant, { strictDisplay = false } = {}) {
  if (trust === null || trust === undefined) {
    throw new Refusal("NO_TRUST_CONFIG", "a reader trust config is required; the document cannot supply one");
  }
  const bare = latin1(pdf.subarray(0, 9)) === '{"blobs":';
  const raw = bare ? pdf : await extract(pdf);
  const { records, blobs } = await decodeBundle(raw);
  let report;
  try {
    const files = {};
    for (const [name, rec] of Object.entries(records)) {
      const bytes = utf8.encode(JSON.stringify(rec));
      if (warrant.recordId(bytes) !== name) throw new Refusal("NAME_MISMATCH", `record ${name} does not hash to its name`);
      files[`records/${name}.json`] = bytes;
    }
    for (const [name, data] of Object.entries(blobs)) files[`blobs/${name}`] = data;
    report = warrant.verifyStore(files, { trust });
  } catch (e) {
    if (e instanceof Refusal) throw e;
    throw new Refusal("WARRANT", `the reader's verifier produced no report: ${e.message ?? e}`);
  }
  const unexpected = report.findings.filter((f) => f.message !== EXPECTED_WARNING || f.level !== "WARN");
  if (!report.ok || report.errors || unexpected.length) {
    const f = (unexpected.length ? unexpected : report.findings.length ? report.findings : [{ message: "not ok" }])[0];
    throw new Refusal("WARRANT", `${f.level ?? ""} ${(f.subject ?? "").slice(0, 16)} ${f.message}`.trim());
  }
  const profileHash = await sha256hex(utf8.encode(`{"profile":"${PROFILE}"}`));
  const { terms, propose, accepts } = arrange(records, blobs, profileHash);
  const text = canonicalText(terms, propose, accepts);
  let display = "NO_PAGE";
  if (!bare) display = equalBytes(await render(text, encodeBundle(records, blobs)), pdf) ? "MATCH" : "DIFFERS";
  if (display === "DIFFERS" && strictDisplay) {
    throw new Refusal("DISPLAY_DIFFERS", "the file is not the canonical rendering of what was signed");
  }
  const signers = [propose, ...accepts].map(([, r]) => [r.body.decision, r.body.actor.id]);
  return { display, text, signers, grade: report.grade };
}
