#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MD="$ROOT/ActinTrackCV_User_Documentation_Refined.md"
DOCX="$ROOT/ActinTrackCV_User_Documentation_Refined.docx"

if [[ ! -f "$MD" ]]; then
  echo "Missing source Markdown: $MD" >&2
  exit 1
fi

if command -v pandoc >/dev/null 2>&1; then
  pandoc "$MD" \
    -o "$DOCX" \
    --from markdown \
    --toc \
    --toc-depth=2 \
    -V geometry:margin=1in
  echo "Built $DOCX with pandoc."
else
  echo "pandoc not found; using built-in Python fallback DOCX builder." >&2
  python "$ROOT/scripts/build_refined_user_documentation.py"
fi
