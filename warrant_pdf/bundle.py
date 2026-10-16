"""The warrant bundle: a warrant store serialized into one JSON byte string,
and its single marked place inside a PDF (ADR-0004)."""
import base64
import binascii
import hashlib
import json
import re
from pathlib import Path

from .profile import PROFILE, Refusal, is_hex64

MARKER = b"%WARRANT-PDF-BUNDLE/"
MARKER_LINE = re.compile(rb"%WARRANT-PDF-BUNDLE/0 len=(\d{1,9}) sha256=([0-9a-f]{64})\n")
# The browser profile of warrant's WASM verifier: 8 MiB of store input, 2,048 files.
# The encoded bundle is larger than the store it decodes to, so this bound suffices.
MAX_BUNDLE = 8 * 1024 * 1024
MAX_ENTRIES = 2048


def _no_constants(name):
    raise ValueError(f"{name} is not JSON")


def encode(records, blobs):
    doc = {"bundle": PROFILE,
           "records": records,
           "blobs": {h: base64.b64encode(b).decode() for h, b in blobs.items()}}
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def decode(raw):
    """Returns (records, blobs). Blob names are checked here; record names need
    the reader's warrant (`canon`) and are checked by the verifier."""
    if len(raw) > MAX_BUNDLE:
        raise Refusal("BUNDLE_LIMIT", f"bundle larger than {MAX_BUNDLE} bytes")
    try:
        doc = json.loads(raw.decode("utf-8"), parse_constant=_no_constants)
    except (UnicodeDecodeError, ValueError) as e:
        raise Refusal("BUNDLE_MALFORMED", str(e))
    if not isinstance(doc, dict) or set(doc) != {"bundle", "records", "blobs"} or doc["bundle"] != PROFILE:
        raise Refusal("BUNDLE_MALFORMED", "top-level fields")
    records, blobs = doc["records"], {}
    if not isinstance(records, dict) or not isinstance(doc["blobs"], dict):
        raise Refusal("BUNDLE_MALFORMED", "records/blobs must be objects")
    if len(records) + len(doc["blobs"]) > MAX_ENTRIES:
        raise Refusal("BUNDLE_LIMIT", f"more than {MAX_ENTRIES} entries")
    for name, rec in records.items():
        if not is_hex64(name) or not isinstance(rec, dict) or set(rec) != {"body", "sigs"}:
            raise Refusal("BUNDLE_MALFORMED", f"record entry {name[:80]!r}")
    for name, b64 in doc["blobs"].items():
        if not is_hex64(name) or not isinstance(b64, str):
            raise Refusal("BUNDLE_MALFORMED", f"blob entry {name[:80]!r}")
        try:
            data = base64.b64decode(b64, validate=True)
        except binascii.Error as e:
            raise Refusal("BUNDLE_MALFORMED", f"blob {name}: {e}")
        if hashlib.sha256(data).hexdigest() != name:
            raise Refusal("NAME_MISMATCH", f"blob {name} does not hash to its name")
        blobs[name] = data
    return records, blobs


def embed_object(bundle_bytes):
    """The marker line and stream of the embedded-file object."""
    head = b"%%WARRANT-PDF-BUNDLE/0 len=%d sha256=%s\n" % (
        len(bundle_bytes), hashlib.sha256(bundle_bytes).hexdigest().encode())
    return head + b"stream\n" + bundle_bytes + b"\nendstream"


def extract(pdf):
    """Exactly one marker at a line start, a matching length and digest."""
    starts = [m.start() for m in re.finditer(re.escape(MARKER), pdf)
              if m.start() == 0 or pdf[m.start() - 1:m.start()] in (b"\n", b"\r")]
    if not starts:
        raise Refusal("BUNDLE_MISSING", "no bundle marker")
    if len(starts) != 1:
        raise Refusal("BUNDLE_AMBIGUOUS", f"{len(starts)} bundle markers")
    m = MARKER_LINE.match(pdf, starts[0])
    if not m:
        raise Refusal("BUNDLE_MALFORMED", "marker line")
    length, digest = int(m.group(1)), m.group(2).decode()
    if length > MAX_BUNDLE:
        raise Refusal("BUNDLE_LIMIT", f"bundle larger than {MAX_BUNDLE} bytes")
    pos = m.end()
    if pdf[pos:pos + 7] != b"stream\n":
        raise Refusal("BUNDLE_MALFORMED", "stream keyword")
    data = pdf[pos + 7:pos + 7 + length]
    if len(data) != length or pdf[pos + 7 + length:pos + 7 + length + 10] != b"\nendstream":
        raise Refusal("BUNDLE_MALFORMED", "stream length")
    if hashlib.sha256(data).hexdigest() != digest:
        raise Refusal("BUNDLE_DIGEST", "bundle bytes do not match the marker digest")
    return data


def read_store(store):
    store = Path(store)
    records = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((store / "records").glob("*.json"))}
    blobs = {p.name: p.read_bytes() for p in sorted((store / "blobs").iterdir())}
    return records, blobs


def write_store(store, records, blobs):
    store = Path(store)
    (store / "records").mkdir(parents=True)
    (store / "blobs").mkdir()
    for name, rec in records.items():
        (store / "records" / f"{name}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    for name, data in blobs.items():
        (store / "blobs" / name).write_bytes(data)
