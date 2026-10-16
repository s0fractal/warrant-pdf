"""Verify a contract PDF under the reader's trust config.

Order: extract the bundle (ADR-0004) -> names (ADR-0004) -> the reader's
warrant at settlement grade (ADR-0003) -> profile rules (ADR-0002) ->
display (ADR-0005). The first refusal ends verification."""
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import bundle, wcli
from .profile import PROFILE_BLOB_HASH, Refusal, canonical_text, parse_terms

# Expected, so not shown: the propose is a root nobody adopted, because a
# two-party contract has no genesis (ADR-0003).
EXPECTED_WARNING = "unadopted root"


@dataclass
class Result:
    display: str  # "MATCH", "DIFFERS", or "NO_PAGE" for a bare bundle
    text: list
    signers: list
    grade: str = ""  # the grade the reader's warrant reported
    warnings: list = field(default_factory=list)


def arrange(records, blobs):
    """Profile rules on bodies (ADR-0002). Returns (terms, propose, accepts)."""
    proposes = [(w, r) for w, r in records.items() if r["body"].get("decision") == "propose"]
    if len(proposes) != 1:
        raise Refusal("PROFILE_PROPOSE", f"{len(proposes)} propose records; exactly one required")
    pid, prop = proposes[0]
    body = prop["body"]
    accepts, others = [], []
    for w, r in sorted(records.items(), key=lambda kv: (kv[1]["body"].get("ts", 0), kv[0])):
        if w == pid:
            continue
        (accepts if r["body"].get("decision") == "accept" else others).append((w, r))
    if others:
        raise Refusal("PROFILE_FOREIGN_RECORD", f"record {others[0][0]} is neither the propose nor an accept")
    for w, r in [(pid, prop)] + accepts:
        if r["body"].get("under") != [PROFILE_BLOB_HASH]:
            raise Refusal("PROFILE_UNDER", f"record {w} is not filed under {PROFILE_BLOB_HASH}")
    terms_hash = body["subject"]["hash"]
    if terms_hash not in blobs:
        raise Refusal("PROFILE_TERMS", "the terms blob named by the propose subject is not in the bundle")
    terms = parse_terms(blobs[terms_hash])
    required = {terms_hash} | {a["sha256"] for a in terms["attachments"]}
    if not required <= set(body["evidence"]):
        raise Refusal("PROFILE_EVIDENCE", "the propose evidence does not list the terms and every attachment")
    absent = [a["name"] for a in terms["attachments"] if a["sha256"] not in blobs]
    if absent:
        # warrant reports an unresolvable evidence blob as a WARN (THREAT-MODEL A5);
        # a contract whose signed photo is missing is not shown as signed.
        raise Refusal("PROFILE_ATTACHMENT_MISSING", f"attachment {absent[0]} is not in the bundle")
    for w, r in accepts:
        b = r["body"]
        if b["prior"] != [pid]:
            raise Refusal("PROFILE_PRIOR", f"accept {w} does not respond to exactly the propose")
        if b["subject"] != body["subject"]:
            raise Refusal("PROFILE_SUBJECT", f"accept {w} names another subject")
        if b["actor"]["id"] == body["actor"]["id"]:
            raise Refusal("PROFILE_SELF_ACCEPT", f"accept {w} is by the proposer")
    signed = {body["actor"]["id"]} | {r["body"]["actor"]["id"] for _, r in accepts}
    missing = [p for p in terms["parties"] if p not in signed]
    if missing:
        raise Refusal("PROFILE_PARTY_UNSIGNED", f"named party {missing[0]} has no record")
    if not accepts:
        raise Refusal("PROFILE_NO_ACCEPT", "nobody accepted")
    return terms, (pid, prop), accepts


def _run_warrant(cmd, records, blobs, trust_config):
    """Record names, then the store, through the reader's warrant."""
    with tempfile.TemporaryDirectory() as tmp:
        for name, rec in records.items():
            if wcli.warrant_id(cmd, rec["body"], tmp) != name:
                raise Refusal("NAME_MISMATCH", f"record {name} does not hash to its name")
        store = Path(tmp) / "store"
        bundle.write_store(store, records, blobs)
        code, report = wcli.verify_store(cmd, store, trust_config)
    if code != 0 and report["ok"]:
        raise wcli.WarrantError(f"exit {code} with ok:true")
    return report


def verify(pdf, trust_config, cmd="warrant", strict_display=False):
    if trust_config is None or not Path(trust_config).is_file():
        raise Refusal("NO_TRUST_CONFIG", "a reader trust config is required; the document cannot supply one")
    # A bare bundle (the attachment, saved from any viewer) verifies the same way;
    # there is no page to compare (ADR-0004, WPDF-E3).
    bare = pdf.startswith(b'{"blobs":')
    raw = pdf if bare else bundle.extract(pdf)
    records, blobs = bundle.decode(raw)
    try:
        report = _run_warrant(cmd, records, blobs, trust_config)
    except (wcli.WarrantError, OSError) as e:
        raise Refusal("WARRANT", f"the reader's verifier produced no report: {e}")
    # WPDF-T2: with --require-bound, every record's own actor signed with a bound key
    # or warrant reported an ERR. Warnings (an excluded co-signature, say) do not
    # refuse; they are shown to the reader.
    errors = [f for f in report["findings"] if f["level"] != "WARN"]
    if not report["ok"] or report["errors"] or errors:
        f = (errors or [{"message": "not ok"}])[0]
        raise Refusal("WARRANT", f"{f.get('level', '')} {f.get('subject', '')[:16]} {f['message']}".strip())
    warnings = [f"{f['subject'][:12]} {f['message']}" for f in report["findings"]
                if f["message"] != EXPECTED_WARNING]
    terms, propose, accepts = arrange(records, blobs)
    from .make import pdf_from
    if bare:
        display = "NO_PAGE"
    else:
        display = "MATCH" if pdf_from(records, blobs) == pdf else "DIFFERS"
    if display == "DIFFERS" and strict_display:
        raise Refusal("DISPLAY_DIFFERS", "the file is not the canonical rendering of what was signed")
    signers = [(r["body"]["decision"], r["body"]["actor"]["id"]) for _, r in [propose] + accepts]
    return Result(display, canonical_text(terms, propose, accepts), signers, report["grade"], warnings)
