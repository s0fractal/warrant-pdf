#!/bin/sh
# Everything CI runs, in the same order. Needs python3 >= 3.11, node >= 22, and the
# `warrant` command (pip install warrant-verify==0.11.0). MUTATE=0 skips mutants;
# NPM=1 also compares the vendored verifier with the tarball npm serves.
set -eu
cd "$(dirname "$0")/.."
export WPDF_REQUIRE_JS=1
echo "== warrant: $(command -v warrant); node: $(node --version)"
python3 tools/vendor_check.py ${NPM:+--against-npm}
python3 demo/build_demo.py --check
python3 tools/contracts.py check
python3 -m unittest discover -s tests
if [ "${MUTATE:-1}" != 0 ]; then
  python3 tools/contracts.py mutate
fi
echo "== local CI passed"
