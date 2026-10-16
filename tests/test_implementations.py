"""ADR-0006: the second implementation exists, ran, and runs a pinned verifier."""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import test_counter_vectors as cv  # noqa: E402
import vendor_check  # noqa: E402
from warrant_pdf.verify import verify as py_verify  # noqa: E402


class Implementations(unittest.TestCase):

    def test_both_implementations_ran_and_agree_on_the_demo(self):
        """Not vacuous: node is present and the JS verdict equals Python's, field by field.
        witness: WPDF-I1"""
        self.assertIsNotNone(cv.NODE, "node not found; the parity hook would be skipped")
        r = py_verify(cv.PDF, cv.TRUST, cv.CMD)
        js = cv.js_outcome(cv.PDF, cv.TRUST, None)
        self.assertEqual(js, ("VERIFIED", r.display, r.signers, r.text, r.grade, r.warnings))
        self.assertEqual(js[1], "MATCH")

    def test_vendored_verifier_matches_its_pin(self):
        """witness: WPDF-I2"""
        self.assertEqual(vendor_check.check_offline(), [])

    def test_tampered_vendored_verifier_is_refused(self):
        """One appended byte in the WASM wrapper, or a swapped WASM, breaks the pin.
        witness: WPDF-I2"""
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "v"
            shutil.copytree(vendor_check.VENDOR, copy)
            with open(copy / "mod.js", "a") as f:
                f.write("//")
            self.assertNotEqual(vendor_check.check_offline(copy), [])
            shutil.copy(vendor_check.VENDOR / "mod.js", copy / "mod.js")
            self.assertEqual(vendor_check.check_offline(copy), [])
            b = copy / "generated" / "bytes.js"
            b.write_text(re.sub(r'"A', '"B', b.read_text(), count=1))
            self.assertNotEqual(vendor_check.check_offline(copy), [])
            # The manifest catches that first; the WASM-to-build.json check is the second,
            # independent line (it holds even after a careless `--write`).
            self.assertTrue(vendor_check.wasm_matches_build(vendor_check.VENDOR))
            self.assertFalse(vendor_check.wasm_matches_build(copy))


if __name__ == "__main__":
    unittest.main()
