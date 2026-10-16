"""Build demo/contract.pdf and demo/trust.json reproducibly.

TEST KEYS ONLY: the secret keys are SHA-256 of public labels, so anyone can
recompute them. They exist to make the demo byte-reproducible; never reuse them.

    python3 demo/build_demo.py            # write demo/contract.pdf, demo/trust.json
    python3 demo/build_demo.py --check    # fail if the committed files differ
"""
import hashlib
import json
import struct
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from warrant_pdf import make, wcli  # noqa: E402

TS = 1792108800  # 2026-10-16T00:00:00Z
PARTIES = {"alice@demo.test": "warrant-pdf demo test key: alice",
           "bob@demo.test": "warrant-pdf demo test key: bob"}
TERMS = {"profile": "warrant-pdf/0",
         "title": "Handover of a bicycle (demo)",
         "clauses": ["Alice hands over the bicycle shown in photo.png to Bob on 2026-10-16.",
                     "Bob confirms the condition shown in the photo, including the scratch on the frame.",
                     "The price is 100 EUR, paid in cash at handover."],
         "parties": list(PARTIES)}


def png(width=32, height=24):
    """A tiny synthetic image, deterministic (stands in for a photo)."""
    rows = b"".join(b"\x00" + b"".join(bytes((x * 8 % 256, y * 10 % 256, (x ^ y) * 7 % 256))
                                       for x in range(width)) for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def keyfiles(tmp):
    out = {}
    for actor, label in PARTIES.items():
        p = Path(tmp) / f"{actor}.key"
        p.write_text(hashlib.sha256(label.encode()).hexdigest() + "\n")
        out[actor] = p
    return out


def build(cmd="warrant"):
    with tempfile.TemporaryDirectory() as tmp:
        keys = keyfiles(tmp)
        (alice, akey), (bob, bkey) = keys.items()
        pdf = make.build(cmd, TERMS, {"photo.png": png()}, (alice, akey),
                         [(bob, bkey, "I saw the terms and the photo before signing.")], TS)
        trust_path = Path(tmp) / "trust.json"
        for actor, key in keys.items():
            wcli.checked(cmd, ["trust", "add", "--actor", actor, "--key", str(key), "--config", "trust.json"],
                         cwd=tmp)
        trust = json.dumps(json.loads(trust_path.read_text()), indent=2, sort_keys=True) + "\n"
    return pdf, trust.encode()


def main():
    pdf, trust = build()
    targets = {ROOT / "demo" / "contract.pdf": pdf, ROOT / "demo" / "trust.json": trust}
    if "--check" in sys.argv:
        stale = [p.name for p, b in targets.items() if not p.is_file() or p.read_bytes() != b]
        if stale:
            sys.exit(f"stale demo files: {stale}; run python3 demo/build_demo.py")
        print("demo files reproduce byte for byte")
        return
    for p, b in targets.items():
        p.write_bytes(b)
        print(f"wrote {p.relative_to(ROOT)} ({len(b)} bytes, sha256 {hashlib.sha256(b).hexdigest()[:16]})")


if __name__ == "__main__":
    main()
