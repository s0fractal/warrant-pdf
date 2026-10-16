"""Profile constants, the terms document, and the canonical text of a contract."""
import hashlib
import json
import re
from datetime import datetime, timezone

PROFILE = "warrant-pdf/0"
# The policy blob every record of this profile files `under` (ADR-0002).
PROFILE_BLOB = json.dumps({"profile": PROFILE}, sort_keys=True, separators=(",", ":")).encode()
PROFILE_BLOB_HASH = hashlib.sha256(PROFILE_BLOB).hexdigest()

HEX64 = re.compile(r"[0-9a-f]{64}")
TERMS_FIELDS = {"profile", "title", "clauses", "parties", "attachments"}


class Refusal(Exception):
    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def _no_constants(name):
    raise ValueError(f"{name} is not JSON")


def is_hex64(value):
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def encode_terms(terms):
    return json.dumps(terms, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def parse_terms(raw):
    try:
        terms = json.loads(raw.decode("utf-8"), parse_constant=_no_constants)
    except (UnicodeDecodeError, ValueError) as e:
        raise Refusal("TERMS_MALFORMED", str(e))
    if not isinstance(terms, dict) or set(terms) != TERMS_FIELDS:
        raise Refusal("TERMS_MALFORMED", f"fields must be exactly {sorted(TERMS_FIELDS)}")
    if terms["profile"] != PROFILE:
        raise Refusal("TERMS_MALFORMED", "unknown profile")
    if not isinstance(terms["title"], str) or not terms["title"]:
        raise Refusal("TERMS_MALFORMED", "title")
    if not isinstance(terms["clauses"], list) or not all(isinstance(c, str) for c in terms["clauses"]):
        raise Refusal("TERMS_MALFORMED", "clauses")
    parties = terms["parties"]
    if not isinstance(parties, list) or not all(isinstance(p, str) and p for p in parties) \
            or len(set(parties)) != len(parties):
        raise Refusal("TERMS_MALFORMED", "parties")
    for a in terms["attachments"] if isinstance(terms["attachments"], list) else [None]:
        if not isinstance(a, dict) or set(a) != {"name", "sha256"} or not isinstance(a["name"], str) \
                or not is_hex64(a["sha256"]):
            raise Refusal("TERMS_MALFORMED", "attachments")
    return terms


MAX_ISO_TS = 253402300799  # 9999-12-31T23:59:59Z


def iso(ts):
    """Total over warrant's ts domain (0..2^53-1): years past 9999 are written as `unix N`."""
    if ts > MAX_ISO_TS:
        return f"unix {ts}"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_text(terms, propose, accepts):
    """What the parties signed, as lines. The PDF page is a rendering of exactly this."""
    lines = [f"WARRANT-PDF/0 CONTRACT", "", f"Title: {terms['title']}", ""]
    lines += [f"{i}. {c}" for i, c in enumerate(terms["clauses"], 1)] or ["(no clauses)"]
    lines += ["", "Named parties: " + (", ".join(terms["parties"]) or "(none named)")]
    lines += ["", "Attachments (SHA-256 of the exact bytes):"]
    lines += [f"  {a['name']}  {a['sha256']}" for a in terms["attachments"]] or ["  (none)"]
    lines += ["", "Signed records (warrant):"]
    for wid, rec in [propose] + accepts:
        body = rec["body"]
        lines.append(f"  {body['decision']} by {body['actor']['id']} at {iso(body['ts'])}")
        lines.append(f"    record {wid}")
        for s in rec["sigs"]:
            lines.append(f"    key {s['key']}")
    lines += ["", "This page is a rendering. The signed content is the embedded",
              "warrant bundle; `python3 -m warrant_pdf verify FILE --trust YOURS.json`",
              "checks the signatures under your trust config and whether this page",
              "matches a fresh rendering of what was signed."]
    return lines
