#!/usr/bin/env python3
"""Check that every LaTeX citation key in main.tex exists in references.bib."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEX_PATH = ROOT / "final-ieee" / "main.tex"
BIB_PATH = ROOT / "final-ieee" / "references.bib"


def main() -> None:
    tex = TEX_PATH.read_text(encoding="utf-8")
    bib = BIB_PATH.read_text(encoding="utf-8")

    cited: set[str] = set()
    for match in re.finditer(r"\\cite\{([^}]+)\}", tex):
        cited.update(key.strip() for key in match.group(1).split(","))

    defined = set(re.findall(r"@\w+\{([^,\s]+)", bib))
    missing = sorted(cited - defined)
    unused = sorted(defined - cited)

    if missing:
        print("Missing BibTeX keys:")
        for key in missing:
            print(f"  - {key}")
        raise SystemExit(1)

    print(f"All {len(cited)} cited BibTeX keys are defined.")
    if unused:
        print("Unused BibTeX keys:")
        for key in unused:
            print(f"  - {key}")


if __name__ == "__main__":
    main()
