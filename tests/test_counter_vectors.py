"""Counter-vectors: each test builds one attack or accident on the demo contract
and names the outcome it must produce. `witness:` lines bind a test to the
normative statement it witnesses (contracts/, tools/contracts.py)."""
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
import build_demo  # noqa: E402
from warrant_pdf import bundle, make, render, wcli  # noqa: E402
from warrant_pdf.profile import PROFILE_BLOB, Refusal, encode_terms  # noqa: E402
from warrant_pdf.verify import verify as py_verify  # noqa: E402

import os  # noqa: E402
import subprocess  # noqa: E402

CMD = "warrant"
NODE = shutil.which("node")
if os.environ.get("WPDF_REQUIRE_JS") == "1" and not NODE:
    raise SystemExit("WPDF_REQUIRE_JS=1 but node is not on PATH")


def js_outcome(pdf, trust, strict_display):
    """The JavaScript implementation (web/profile.mjs on warrant's Rust core in WASM)."""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "input"
        f.write_bytes(pdf)
        args = [NODE, str(ROOT / "web" / "cli.mjs"), str(f), str(trust) if trust is not None else "-"]
        flag = {None: [], True: ["--strict-display"], False: ["--no-strict-display"]}[strict_display]
        out = subprocess.run(args + flag,
                             capture_output=True, text=True)
    if out.returncode != 0:
        raise AssertionError(f"JS verifier crashed: {out.stderr.strip()[-400:]}")
    d = json.loads(out.stdout)
    if d["outcome"] == "REFUSED":
        return ("REFUSED", d["code"])
    return ("VERIFIED", d["display"], [tuple(x) for x in d["signers"]], d["text"], d["grade"], d["warnings"])


def verify(pdf, trust, cmd, **kw):
    """Both implementations of the profile must agree on every input (parity).
    The JS side always uses warrant's WASM core; it is skipped only when the test
    deliberately breaks the Python side's verifier command."""
    try:
        r = py_verify(pdf, trust, cmd, **kw)  # defaults stay the implementation's own
        py, err = ("VERIFIED", r.display, r.signers, r.text, r.grade, r.warnings), None
    except Refusal as e:
        py, err = ("REFUSED", e.code), e
    if NODE and cmd == CMD:
        js = js_outcome(pdf, trust, kw.get("strict_display"))
        if js != py:
            raise AssertionError(f"Python and JS disagree:\n  python: {py[:2]}\n  js:     {js[:2]}")
    if err:
        raise err
    return r
PDF = (ROOT / "demo" / "contract.pdf").read_bytes()
TRUST = ROOT / "demo" / "trust.json"
ALICE, BOB = list(build_demo.PARTIES)


def parts(pdf=PDF):
    return bundle.decode(bundle.extract(pdf))


def rebuild(records, blobs):
    """A well-formed PDF around an arbitrary bundle (the attacker's tool)."""
    from warrant_pdf.profile import canonical_text  # noqa: F401
    return render.render(["(attacker rendering)"], bundle.encode(records, blobs))


class Scenario:
    """A fresh warrant store with the demo terms and keys, for re-signing."""

    def __init__(self, parties=None):
        self.tmp = Path(tempfile.mkdtemp())
        self.keys = build_demo.keyfiles(self.tmp)
        self.mallory = self.tmp / "mallory.key"
        self.mallory.write_text(hashlib.sha256(b"mallory").hexdigest() + "\n")
        terms = dict(build_demo.TERMS, parties=list(build_demo.PARTIES) if parties is None else parties,
                     attachments=[{"name": "photo.png",
                                                     "sha256": hashlib.sha256(build_demo.png()).hexdigest()}])
        self.terms = self.tmp / "terms.json"
        self.terms.write_bytes(encode_terms(terms))
        self.photo = self.tmp / "photo.png"
        self.photo.write_bytes(build_demo.png())
        self.profile = self.tmp / "profile.json"
        self.profile.write_bytes(PROFILE_BLOB)
        self.store = self.tmp / "store"
        self.w("init")
        for p in (self.profile, self.terms, self.photo):
            self.w("blob", "add", str(p))

    def w(self, *args):
        return wcli.checked(CMD, ["--store", str(self.store), *args]).strip().splitlines()[-1]

    def propose(self, actor=None, key=None, under=None, evidence=("terms", "photo"), ts=build_demo.TS):
        ev = []
        for e in evidence:
            ev += ["--evidence", str(getattr(self, e))]
        return self.w("propose", "--subject", str(self.terms), "--under", str(under or self.profile),
                      "--note", "x", *ev, "--actor", actor or ALICE,
                      "--key", str(key or self.keys[ALICE]), "--ts", str(ts))

    def accept(self, prior, actor=None, key=None, ts=build_demo.TS + 1):
        return self.w("accept", prior, "--reason", "ok", "--actor", actor or BOB,
                      "--key", str(key or self.keys[BOB]), "--ts", str(ts))

    def pdf(self):
        """The canonical rendering when the profile allows one, else an attacker's."""
        records, blobs = bundle.read_store(self.store)
        try:
            return make.pdf_from(records, blobs)
        except Refusal:
            return rebuild(records, blobs)

    def cleanup(self):
        shutil.rmtree(self.tmp)


class CounterVectors(unittest.TestCase):

    def refused(self, pdf, code, trust=TRUST, cmd=CMD, **kw):
        with self.assertRaises(Refusal) as cm:
            verify(pdf, trust, cmd, **kw)
        self.assertEqual(cm.exception.code, code, cm.exception.detail)

    def scenario(self, parties=None):
        s = Scenario(parties)
        self.addCleanup(s.cleanup)
        return s

    def trust_with(self, s, actor, key):
        wcli.checked(CMD, ["trust", "add", "--actor", actor, "--key", str(key), "--config", "trust.json"],
                     cwd=s.tmp)
        cfg = json.loads(TRUST.read_text())
        cfg["actors"].update(json.loads((s.tmp / "trust.json").read_text())["actors"])
        (s.tmp / "trust.json").write_text(json.dumps(cfg))
        return s.tmp / "trust.json"

    # --- baseline -----------------------------------------------------------

    def test_demo_verifies_and_page_matches(self):
        """witness: WPDF-D1"""
        r = verify(PDF, TRUST, CMD)
        self.assertEqual(r.display, "MATCH")
        self.assertEqual(r.signers, [("propose", ALICE), ("accept", BOB)])

    def test_demo_rebuilds_byte_for_byte(self):
        """witness: WPDF-D2"""
        pdf, trust = build_demo.build(CMD)
        self.assertEqual(pdf, PDF)
        self.assertEqual(trust, TRUST.read_bytes())

    def test_scenario_baseline_verifies(self):
        """The re-signing harness itself produces an accepted contract (honest positive)."""
        s = self.scenario()
        s.accept(s.propose())
        self.assertEqual(verify(s.pdf(), TRUST, CMD).display, "MATCH")

    # --- embedding (ADR-0004) ----------------------------------------------

    def test_no_marker_refuses(self):
        """witness: WPDF-E1"""
        self.refused(PDF.replace(b"%WARRANT-PDF-BUNDLE/0", b"%WARRANT-PDF-BUNDLX/0"), "BUNDLE_MISSING")

    def test_second_bundle_appended_refuses(self):
        """An incremental update that carries a second, valid bundle.
        witness: WPDF-E1"""
        second = b"\n99 0 obj\n<< /Type /EmbeddedFile >>\n" + bundle.embed_object(bundle.extract(PDF)) + b"\nendobj\n"
        self.refused(PDF + second, "BUNDLE_AMBIGUOUS")

    def test_bundle_byte_flipped_refuses(self):
        """witness: WPDF-E1"""
        raw = bundle.extract(PDF)
        i = PDF.index(raw) + len(raw) // 2
        self.refused(PDF[:i] + bytes([PDF[i] ^ 1]) + PDF[i + 1:], "BUNDLE_DIGEST")

    def test_blob_bytes_changed_under_old_name_refuses(self):
        """witness: WPDF-E2"""
        records, blobs = parts()
        name = hashlib.sha256(build_demo.png()).hexdigest()
        blobs[name] = blobs[name] + b"x"
        self.refused(rebuild(records, blobs), "NAME_MISMATCH")

    def test_record_under_wrong_name_refuses(self):
        """witness: WPDF-E2"""
        records, blobs = parts()
        (a, ra), (b, rb) = records.items()
        self.refused(rebuild({a: rb, b: ra}, blobs), "NAME_MISMATCH")

    def test_photo_swapped_and_renamed_refuses(self):
        """A different photo under its own correct name: the signed evidence no longer resolves.
        warrant only warns about an unresolvable evidence blob, so the profile must refuse.
        witness: WPDF-P1"""
        records, blobs = parts()
        old = hashlib.sha256(build_demo.png()).hexdigest()
        new = build_demo.png(33, 24)
        del blobs[old]
        blobs[hashlib.sha256(new).hexdigest()] = new
        self.refused(rebuild(records, blobs), "PROFILE_ATTACHMENT_MISSING")

    def test_attachment_saved_from_a_viewer_verifies(self):
        """A PDF tool re-saved the file and dropped the marker line; the attachment survived.
        witness: WPDF-E3"""
        r = verify(bundle.extract(PDF), TRUST, CMD)
        self.assertEqual(r.display, "NO_PAGE")
        self.assertEqual(r.signers, [("propose", ALICE), ("accept", BOB)])

    def test_bare_bundle_gets_the_same_checks(self):
        """A bare bundle is no shortcut around the name checks.
        witness: WPDF-E3"""
        records, blobs = parts()
        (a, ra), (b, rb) = records.items()
        with self.assertRaises(Refusal) as cm:
            verify(bundle.encode({a: rb, b: ra}, blobs), TRUST, CMD)
        self.assertEqual(cm.exception.code, "NAME_MISMATCH")

    def test_nan_in_bundle_refuses(self):
        """Python's json accepts NaN; JSON does not, and a browser verifier would refuse.
        witness: WPDF-E4"""
        raw = bundle.extract(PDF).decode()
        self.refused(raw.replace('"sigs":[', '"sigs":[NaN,', 1).encode(), "BUNDLE_MALFORMED")

    def test_more_entries_than_the_browser_verifier_admits_refuses(self):
        """witness: WPDF-E4"""
        records, blobs = parts()
        for i in range(2049 - len(records) - len(blobs)):
            data = b"%d" % i
            blobs[hashlib.sha256(data).hexdigest()] = data
        self.refused(rebuild(records, blobs), "BUNDLE_LIMIT")

    def test_oversized_bundle_is_refused_before_reading(self):
        """witness: WPDF-E4"""
        forged = re.sub(rb"len=\d+", b"len=8388609", PDF, count=1)
        self.refused(forged, "BUNDLE_LIMIT")

    # --- trust (ADR-0003) --------------------------------------------------

    def test_without_reader_trust_refuses(self):
        """witness: WPDF-T1"""
        self.refused(PDF, "NO_TRUST_CONFIG", trust=None)

    def test_counterparty_not_in_reader_trust_refuses(self):
        """witness: WPDF-T1"""
        cfg = json.loads(TRUST.read_text())
        del cfg["actors"][BOB]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "trust.json"
            p.write_text(json.dumps(cfg))
            self.refused(PDF, "WARRANT", trust=p)

    def test_accept_signed_by_another_key_for_the_same_actor_refuses(self):
        """Mallory files `accept` as bob@demo.test with her own key.
        witness: WPDF-T2"""
        s = self.scenario()
        s.accept(s.propose(), key=s.mallory)
        self.refused(s.pdf(), "WARRANT")

    def test_verification_ran_at_settlement_grade(self):
        """Honest positive: Bob's bound key verifies, and the grade is the one that binds keys.
        witness: WPDF-T2"""
        self.assertEqual(verify(PDF, TRUST, CMD).grade, "settlement")

    def test_appended_junk_cosignature_is_excluded_not_fatal(self):
        """Anyone holding a copy can append a co-signature (signatures sit outside the
        WarrantID). An invalid one claiming an unrelated actor is excluded by warrant and
        shown as a warning; the contract still verifies. Until warrant 0.11.0 this profile
        refused here (the limitation pinned in 8b21a6e).
        witness: WPDF-T2"""
        records, blobs = parts()
        acc = next(w for w, r in records.items() if r["body"]["decision"] == "accept")
        records[acc]["sigs"].append({"actor": "carol@demo.test", "key": "00" * 32, "sig": "00" * 64})
        r = verify(rebuild(records, blobs), TRUST, CMD)
        self.assertEqual(r.signers, [("propose", ALICE), ("accept", BOB)])
        self.assertTrue(any("signature does not verify (excluded)" in w for w in r.warnings), r.warnings)

    def test_valid_cosignature_by_an_unbound_key_is_shown_not_fatal(self):
        """A cryptographically valid co-signature by a key nobody bound, claiming another
        actor: warrant reports it unbound; it does not count and does not refuse.
        witness: WPDF-T2"""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        records, blobs = parts()
        acc = next(w for w, r in records.items() if r["body"]["decision"] == "accept")
        k = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b"junk").digest())
        records[acc]["sigs"].append({"actor": "carol@demo.test", "key": k.public_key().public_bytes_raw().hex(),
                                     "sig": k.sign(b"warrant-sig-v1:" + bytes.fromhex(acc)).hex()})
        r = verify(rebuild(records, blobs), TRUST, CMD)
        self.assertTrue(any("signature unbound" in w and "carol@demo.test" in w for w in r.warnings), r.warnings)

    def test_unavailable_verifier_refuses(self):
        """No report is not a pass, and not a crash either.
        witness: WPDF-T2"""
        self.refused(PDF, "WARRANT", cmd="/nonexistent/warrant")

    # --- profile (ADR-0002) ------------------------------------------------

    def test_accept_removed_refuses(self):
        """witness: WPDF-P3"""
        s = self.scenario()
        s.propose()
        self.refused(s.pdf(), "PROFILE_PARTY_UNSIGNED")

    def test_self_accept_refuses(self):
        """witness: WPDF-P2"""
        s = self.scenario()
        s.accept(s.propose(), actor=ALICE, key=s.keys[ALICE])
        self.refused(s.pdf(), "PROFILE_SELF_ACCEPT")

    def test_accept_of_an_offer_not_in_the_bundle_refuses(self):
        """Bob's accept answers an earlier offer; that offer is left out of the bundle.
        Owned by warrant (dangling prior), not by the profile."""
        s = self.scenario()
        old = s.propose(evidence=("terms", "photo", "profile"), ts=build_demo.TS - 10)
        accept = s.accept(old)
        records, _ = bundle.read_store(s.store)
        s2 = self.scenario()
        new = s2.propose()
        r2, b2 = bundle.read_store(s2.store)
        self.refused(rebuild({new: r2[new], accept: records[accept]}, b2), "WARRANT")

    def test_accept_of_an_accept_refuses(self):
        """Carol accepts Bob's accept instead of the offer.
        witness: WPDF-P2"""
        s = self.scenario()
        carol = s.tmp / "carol.key"
        carol.write_text(hashlib.sha256(b"carol").hexdigest() + "\n")
        s.accept(s.accept(s.propose()), actor="carol@demo.test", key=carol, ts=build_demo.TS + 2)
        self.refused(s.pdf(), "PROFILE_PRIOR", trust=self.trust_with(s, "carol@demo.test", carol))

    def test_self_accept_with_no_named_parties_refuses(self):
        """No named party would be missing; only the self-accept rule stands in the way.
        witness: WPDF-P2"""
        s = self.scenario(parties=[])
        s.accept(s.propose(), actor=ALICE, key=s.keys[ALICE])
        self.refused(s.pdf(), "PROFILE_SELF_ACCEPT")

    def test_accept_naming_another_subject_refuses(self):
        """witness: WPDF-P2"""
        s = self.scenario()
        p = s.propose()
        s.w("accept", p, "--subject", str(s.photo), "--reason", "ok", "--actor", BOB,
            "--key", str(s.keys[BOB]), "--ts", str(build_demo.TS + 1))
        self.refused(s.pdf(), "PROFILE_SUBJECT")

    def test_named_party_replaced_by_a_trusted_stranger_refuses(self):
        """Carol (trusted by this reader) accepts; Bob, the named party, never did.
        witness: WPDF-P3"""
        s = self.scenario()
        carol = s.tmp / "carol.key"
        carol.write_text(hashlib.sha256(b"carol").hexdigest() + "\n")
        s.accept(s.propose(), actor="carol@demo.test", key=carol)
        trust = self.trust_with(s, "carol@demo.test", carol)
        self.refused(s.pdf(), "PROFILE_PARTY_UNSIGNED", trust=trust)

    def test_offer_without_any_accept_refuses(self):
        """witness: WPDF-P3"""
        s = self.scenario(parties=[])
        s.propose()
        self.refused(s.pdf(), "PROFILE_NO_ACCEPT")

    def test_second_propose_refuses(self):
        """witness: WPDF-P1"""
        s = self.scenario()
        s.accept(s.propose())
        s.propose(evidence=("terms", "photo", "profile"), ts=build_demo.TS + 5)
        self.refused(s.pdf(), "PROFILE_PROPOSE")

    def test_foreign_record_refuses(self):
        """A valid, trusted `supersede` by the proposer slipped into the bundle.
        (A prose-only `reject` would already be refused: warrant warns on it.)
        witness: WPDF-P1"""
        s = self.scenario()
        p = s.propose()
        s.accept(p)
        s.w("supersede", p, "--reason", "withdrawn", "--actor", ALICE, "--key", str(s.keys[ALICE]),
            "--ts", str(build_demo.TS + 2))
        self.refused(s.pdf(), "PROFILE_FOREIGN_RECORD")

    def test_attachment_not_in_evidence_refuses(self):
        """witness: WPDF-P1"""
        s = self.scenario()
        s.accept(s.propose(evidence=("terms",)))
        self.refused(s.pdf(), "PROFILE_EVIDENCE")

    def test_filed_under_another_policy_refuses(self):
        """witness: WPDF-P1"""
        s = self.scenario()
        other = s.tmp / "other.json"
        other.write_bytes(b'{"profile":"other"}')
        s.w("blob", "add", str(other))
        s.accept(s.propose(under=other))
        self.refused(s.pdf(), "PROFILE_UNDER")

    # --- display (ADR-0005) ------------------------------------------------

    def test_visible_text_edited_is_reported(self):
        """Same length, valid PDF, signatures untouched: the page lies.
        witness: WPDF-D1"""
        forged = PDF.replace(b"The price is 100 EUR", b"The price is 900 EUR", 1)
        self.assertNotEqual(forged, PDF)
        r = verify(forged, TRUST, CMD)
        self.assertEqual(r.display, "DIFFERS")
        self.assertIn("3. The price is 100 EUR, paid in cash at handover.", r.text)
        self.refused(forged, "DISPLAY_DIFFERS", strict_display=True)

    def test_largest_timestamp_warrant_admits_verifies(self):
        """warrant admits ts up to 2^53-1; the year is then far past 9999.
        witness: WPDF-D3"""
        s = self.scenario()
        s.accept(s.propose(ts=2**53 - 2), ts=2**53 - 1)
        r = verify(s.pdf(), TRUST, CMD)
        self.assertEqual(r.display, "MATCH")
        self.assertIn("  accept by bob@demo.test at unix 9007199254740991", r.text)

    def test_re_rendered_elsewhere_still_verifies(self):
        """Another rendering of the same bundle: signatures hold, the page is flagged.
        witness: WPDF-A1"""
        records, blobs = parts()
        r = verify(rebuild(records, blobs), TRUST, CMD)
        self.assertEqual(r.display, "DIFFERS")
        self.assertEqual(r.signers, [("propose", ALICE), ("accept", BOB)])


if __name__ == "__main__":
    unittest.main()
