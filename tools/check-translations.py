#!/usr/bin/env python3
"""Report translatable strings that are missing from a language dictionary.

Parses the source with `ast`, so implicitly concatenated multi-line strings
are seen exactly as the runtime sees them — which is where hand-maintained
translation tables usually drift.

Usage: tools/check-translations.py [language ...]
Exits non-zero when something is missing.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "src" / "tlppanel"

sys.path.insert(0, str(ROOT / "src"))
from tlppanel.i18n import TRANSLATIONS  # noqa: E402


def collect_strings() -> dict[str, list[str]]:
    """Map each translatable literal to the files it appears in."""
    found: dict[str, list[str]] = {}
    for path in sorted(SOURCE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # `_` translates now, `N_` marks a string translated later.
            if not isinstance(node.func, ast.Name) or node.func.id not in ("_", "N_"):
                continue
            if not node.args:
                continue
            first = node.args[0]
            # Only literal strings can be checked ahead of time; values built
            # at runtime are reported separately so they are not forgotten.
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.setdefault(first.value, []).append(path.name)
    return found


def main(argv: list[str]) -> int:
    languages = argv[1:] or sorted(TRANSLATIONS)
    strings = collect_strings()
    print(f"{len(strings)} translatable strings found in {SOURCE_DIR.relative_to(ROOT)}")

    failed = False
    for language in languages:
        table = TRANSLATIONS.get(language)
        if table is None:
            print(f"  {language}: no dictionary")
            failed = True
            continue

        missing = [text for text in strings if text not in table]
        unused = [text for text in table if text not in strings]

        if missing:
            failed = True
            print(f"  {language}: {len(missing)} missing")
            for text in missing:
                where = ", ".join(sorted(set(strings[text])))
                preview = text if len(text) <= 60 else text[:57] + "..."
                print(f"    - {preview!r}  ({where})")
        else:
            print(f"  {language}: complete")

        if unused:
            print(f"  {language}: {len(unused)} unused entries")
            for text in unused:
                preview = text if len(text) <= 60 else text[:57] + "..."
                print(f"    ? {preview!r}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
