"""python3 -m warrant_pdf verify FILE --trust TRUST.json [--warrant CMD] [--strict-display]

FILE is a contract PDF, or the `warrant-bundle.json` attachment saved from one.
Exit 0: verified; the page matches a fresh rendering (or there is no page).
Exit 2: verified, but the page differs (re-exported or edited); read the printed text.
Exit 1: refused; the first line names the reason code."""
import argparse
import sys
from pathlib import Path

from .profile import Refusal
from .verify import verify


def main(argv=None):
    ap = argparse.ArgumentParser(prog="warrant_pdf")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify")
    v.add_argument("file")
    v.add_argument("--trust", required=True, help="your trust config (warrant SPEC §12)")
    v.add_argument("--warrant", default="warrant", help="the warrant verifier to run")
    v.add_argument("--strict-display", action="store_true")
    args = ap.parse_args(argv)
    try:
        r = verify(Path(args.file).read_bytes(), args.trust, args.warrant, args.strict_display)
    except Refusal as e:
        print(f"REFUSED {e.code}: {e.detail}")
        return 1
    print("VERIFIED " + ", ".join(f"{d} by {a}" for d, a in r.signers))
    if r.display == "NO_PAGE":
        print("NO PAGE: a bare bundle was verified; the signed text follows.")
    if r.display == "DIFFERS":
        print("DISPLAY DIFFERS: this file is not the canonical rendering; the signed text follows.")
    print()
    print("\n".join(r.text))
    return 2 if r.display == "DIFFERS" else 0


if __name__ == "__main__":
    sys.exit(main())
