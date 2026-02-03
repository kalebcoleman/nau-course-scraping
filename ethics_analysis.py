#!/usr/bin/env python3
"""
Generate a standalone ethics-related course subset.

Inputs:
  - Course CSV with columns: prefix, number, title, description (plus any others)

Outputs:
  - Ethics-only subset CSV (deduped by prefix + number)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

TITLE_PATTERNS = [
    r"\bethic(s|al)?\b",
    r"\bbioethic(s|al)?\b",
    r"\bcyberethic(s|al)?\b",
]

DESCRIPTION_PATTERNS = [
    r"\bprofessional ethics\b",
    r"\bethical decision[- ]making\b",
    r"\bethical issues?\b",
    r"\bethics and\b",
    r"\bethics of\b",
    r"\bethics in\b",
    r"\bresearch ethics\b",
    r"\bethical standards?\b",
    r"\bethical responsibilities?\b",
    r"\bhealth care ethics\b",
    r"\benvironmental ethics\b",
    r"\bbioethic(s|al)?\b",
    r"\bcyberethic(s|al)?\b",
    r"\bcode of ethics\b",
]


@dataclass(frozen=True)
class EthicsMatcher:
    """Precompiled regex matcher for ethics-related courses."""

    title_patterns: tuple[re.Pattern[str], ...]
    description_patterns: tuple[re.Pattern[str], ...]

    @classmethod
    def build(cls) -> "EthicsMatcher":
        return cls(
            title_patterns=tuple(
                re.compile(pattern, re.IGNORECASE) for pattern in TITLE_PATTERNS
            ),
            description_patterns=tuple(
                re.compile(pattern, re.IGNORECASE)
                for pattern in DESCRIPTION_PATTERNS
            ),
        )

    def is_match(self, title: str | None, description: str | None) -> bool:
        title_text = title or ""
        description_text = description or ""
        if any(p.search(title_text) for p in self.title_patterns):
            return True
        return any(p.search(description_text) for p in self.description_patterns)


def main() -> None:
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover - runtime dependency check
        print(
            "Missing dependency: pandas. Install with: pip install pandas",
            file=sys.stderr,
        )
        raise SystemExit(1)

    parser = argparse.ArgumentParser(
        description="Create an ethics-related course subset."
    )
    parser.add_argument(
        "--input-courses",
        default="outputs/nau_courses.csv",
        help="Path to the course CSV (default: outputs/nau_courses.csv).",
    )
    parser.add_argument(
        "--output",
        default="outputs/nau_courses_ethics_subset.csv",
        help="Output path for the ethics subset (default: outputs/nau_courses_ethics_subset.csv).",
    )
    args = parser.parse_args()

    input_courses = Path(args.input_courses)
    if not input_courses.exists():
        print(f"Course CSV not found: {input_courses}", file=sys.stderr)
        raise SystemExit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_courses)
    required_cols = ["prefix", "number", "title", "description"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"Missing required columns: {missing}", file=sys.stderr)
        raise SystemExit(1)

    matcher = EthicsMatcher.build()
    ethics_flags = [
        matcher.is_match(title, description)
        for title, description in zip(df["title"], df["description"])
    ]
    df["is_ethics_related"] = ethics_flags

    subset = (
        df[df["is_ethics_related"]]
        .drop_duplicates(subset=["prefix", "number"])
        .sort_values(["prefix", "number"])
    )

    subset.to_csv(output_path, index=False)
    print(f"Wrote {len(subset)} ethics courses to {output_path}")


if __name__ == "__main__":
    main()
