"""Build a contract PDF: A proposes, B accepts, both through the warrant CLI."""
import hashlib
import tempfile
from pathlib import Path

from . import bundle, render, wcli
from .profile import PROFILE_BLOB, encode_terms, parse_terms, canonical_text


def file_records(cmd, store, terms_path, attachment_paths, proposer, acceptors, ts):
    """proposer = (actor, keyfile); acceptors = [(actor, keyfile, reason)]."""
    work = Path(store).parent
    profile_path = work / "profile.json"
    profile_path.write_bytes(PROFILE_BLOB)
    wcli.checked(cmd, ["--store", str(store), "init"])
    for p in [profile_path, terms_path, *attachment_paths]:
        wcli.checked(cmd, ["--store", str(store), "blob", "add", str(p)])
    evidence = []
    for p in [terms_path, *attachment_paths]:
        evidence += ["--evidence", str(p)]
    title = parse_terms(Path(terms_path).read_bytes())["title"][:200]
    out = wcli.checked(cmd, ["--store", str(store), "propose", "--subject", str(terms_path),
                             "--under", str(profile_path), "--note", title, *evidence,
                             "--actor", proposer[0], "--key", str(proposer[1]), "--ts", str(ts)])
    propose_id = out.strip().splitlines()[-1]
    for i, (actor, key, reason) in enumerate(acceptors, 1):
        wcli.checked(cmd, ["--store", str(store), "accept", propose_id, "--reason", reason,
                           "--actor", actor, "--key", str(key), "--ts", str(ts + i)])
    return propose_id


def build(cmd, terms, attachments, proposer, acceptors, ts):
    """terms: dict without `attachments`; attachments: {name: bytes}. Returns PDF bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        terms = dict(terms, attachments=[{"name": n, "sha256": hashlib.sha256(b).hexdigest()}
                                         for n, b in sorted(attachments.items())])
        terms_path = tmp / "terms.json"
        terms_path.write_bytes(encode_terms(terms))
        paths = []
        for i, (name, data) in enumerate(sorted(attachments.items())):
            paths.append(tmp / f"attachment-{i}")
            paths[-1].write_bytes(data)
        store = tmp / "store"
        file_records(cmd, store, terms_path, paths, proposer, acceptors, ts)
        records, blobs = bundle.read_store(store)
    return pdf_from(records, blobs)


def pdf_from(records, blobs):
    """The one rendering function; the verifier calls it too (ADR-0005)."""
    from .verify import arrange
    terms, propose, accepts = arrange(records, blobs)
    return render.render(canonical_text(terms, propose, accepts), bundle.encode(records, blobs))
