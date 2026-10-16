"""The vendored warrant WASM package is exactly the published one.

    python3 tools/vendor_check.py               # files match the manifest; WASM matches build.json
    python3 tools/vendor_check.py --against-npm # also: npm's tarball has the pinned integrity
                                                # and the same bytes (needs npm and network)
    python3 tools/vendor_check.py --write       # rewrite the manifest (after a deliberate upgrade)

The browser verifier runs this copy, so this copy is the reader's verifier: it is
pinned by the npm registry's sha512 integrity, and every file by SHA-256."""
import base64
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE, VERSION = "@s0fractal/warrant", "0.11.0"
VENDOR = ROOT / "web" / "vendor" / f"warrant-{VERSION}"
MANIFEST = ROOT / "web" / "vendor" / f"warrant-{VERSION}.json"
INTEGRITY = "sha512-NWu9TcYjPBm6v5/M9FU2YKaf5x0MRkjcRj0MqVvydrzAxLuvLcqG90LAouuh7xdGZqn8nhbliu6h8WNZJURTAw=="
# Tarball path -> vendored path. The package's README and package.json are not needed to run.
LAYOUT = {"package/LICENSE": "LICENSE"} | {
    f"package/dist/{p}": p for p in ("mod.js", "mod.d.ts", "generated/build.json", "generated/bytes.js",
                                    "generated/bytes.d.ts", "generated/warrant_browser.js",
                                    "generated/warrant_browser.d.ts")}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def current(vendor=VENDOR):
    return {rel: sha((vendor / rel).read_bytes()) for rel in sorted(LAYOUT.values())}


def wasm_matches_build(vendor=VENDOR):
    text = (vendor / "generated" / "bytes.js").read_text()
    wasm = base64.b64decode(re.fullmatch(r'export const binary = "([A-Za-z0-9+/=]+)";\s*', text).group(1))
    build = json.loads((vendor / "generated" / "build.json").read_text())
    return sha(wasm) == build["wasmSha256"] and build["packageVersion"] == VERSION and build["workingTree"] == "clean"


def against_npm(manifest):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["npm", "pack", f"{PACKAGE}@{VERSION}", "--pack-destination", tmp, "--ignore-scripts"],
                       check=True, capture_output=True)
        tgz = next(Path(tmp).glob("*.tgz"))
        integrity = "sha512-" + base64.b64encode(hashlib.sha512(tgz.read_bytes()).digest()).decode()
        if integrity != INTEGRITY:
            return [f"npm tarball integrity {integrity} != pinned {INTEGRITY}"]
        errors = []
        with tarfile.open(tgz) as tar:
            for member, rel in LAYOUT.items():
                if sha(tar.extractfile(member).read()) != manifest["files"][rel]:
                    errors.append(f"{rel} differs from the npm tarball")
        return errors


def check_offline(vendor=VENDOR):
    """Errors for a vendored copy; empty when it matches the pin."""
    manifest = json.loads(MANIFEST.read_text())
    present = sorted(str(p.relative_to(vendor)) for p in vendor.rglob("*") if p.is_file())
    if present != sorted(LAYOUT.values()):
        return [f"vendored files {present} != expected {sorted(LAYOUT.values())}"]
    if current(vendor) != manifest["files"] or manifest["npm_integrity"] != INTEGRITY:
        return ["vendored bytes differ from the manifest"]
    if not wasm_matches_build(vendor):
        return ["embedded WASM does not match build.json"]
    return []


def main():
    if "--write" in sys.argv:
        MANIFEST.write_text(json.dumps({"package": PACKAGE, "version": VERSION, "npm_integrity": INTEGRITY,
                                        "files": current()}, indent=2) + "\n")
        print(f"wrote {MANIFEST.relative_to(ROOT)}")
        return 0
    manifest = json.loads(MANIFEST.read_text())
    errors = check_offline()
    if not errors and "--against-npm" in sys.argv:
        errors += against_npm(manifest)
    for e in errors:
        print("FAIL", e)
    print(f"vendored {PACKAGE}@{VERSION}: {'FAIL' if errors else 'ok'}"
          + (" (checked against npm)" if "--against-npm" in sys.argv and not errors else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
