#!/bin/sh
# Everything CI runs, in the same order. Needs python3 >= 3.11 and the `warrant`
# command (pip install warrant-verify==0.10.0). Set MUTATE=0 to skip mutants.
set -eu
cd "$(dirname "$0")/.."
echo "== warrant: $(command -v warrant)"
python3 demo/build_demo.py --check
python3 tools/contracts.py check
python3 -m unittest discover -s tests
if [ "${MUTATE:-1}" != 0 ]; then
  python3 tools/contracts.py mutate
fi
echo "== local CI passed"
