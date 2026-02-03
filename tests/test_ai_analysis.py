import csv
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]
# When running this file directly (`python3 tests/test_ai_analysis.py`), Python sets
# `sys.path[0]` to the tests directory. Add the repo root so we can import scripts
# like `ai_analysis.py` as modules.
sys.path.insert(0, str(REPO_ROOT))


def _deps_available() -> bool:
    try:
        import pandas  # noqa: F401
        import thefuzz  # noqa: F401
    except Exception:
        return False
    return True


HAS_DEPS = _deps_available()


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


@unittest.skipUnless(
    HAS_DEPS, "Requires pandas + thefuzz. Install: pip install pandas thefuzz[speedup]"
)
class TestAiAnalysis(unittest.TestCase):
    def test_normalize_text_ai_punctuation(self) -> None:
        import ai_analysis
        import ai_analysis_broad

        self.assertEqual(ai_analysis.normalize_text("A.I."), "ai")
        self.assertEqual(ai_analysis_broad.normalize_text("A.I."), "ai")

    def test_context_gating_ethics_requires_ai_context(self) -> None:
        import ai_analysis

        primary = ai_analysis.compile_patterns(ai_analysis.PRIMARY_PATTERNS)
        secondary = ai_analysis.compile_patterns(ai_analysis.SECONDARY_PATTERNS)
        context = ai_analysis.compile_patterns(ai_analysis.CONTEXT_PATTERNS)

        # Ethics alone should not be enough to mark a course as AI-related.
        text_norm = ai_analysis.normalize_text("Ethics in Technology")
        keyword_match = ai_analysis.matches_any(text_norm, primary) or (
            ai_analysis.matches_any(text_norm, secondary)
            and ai_analysis.matches_any(text_norm, context)
        )
        self.assertFalse(keyword_match)

        # Ethics + explicit AI context should count.
        text_norm = ai_analysis.normalize_text("Ethics of AI")
        keyword_match = ai_analysis.matches_any(text_norm, primary) or (
            ai_analysis.matches_any(text_norm, secondary)
            and ai_analysis.matches_any(text_norm, context)
        )
        self.assertTrue(keyword_match)

    def test_ai_analysis_dedup_and_unique_flags(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_csv = tmp_path / "courses.csv"
            out_dir = tmp_path / "out"
            out_dir.mkdir()

            _write_csv(
                input_csv,
                [
                    {
                        "term": "Fall 2025",
                        "prefix": "CS",
                        "number": "470",
                        "title": "Artificial Intelligence",
                        "description": "Study of artificial intelligence and intelligent systems.",
                    },
                    {
                        "term": "Spring 2026",
                        "prefix": "CS",
                        "number": "470",
                        "title": "Artificial Intelligence",
                        "description": "Study of artificial intelligence and intelligent systems.",
                    },
                    {
                        "term": "Fall 2025",
                        "prefix": "PHIL",
                        "number": "100",
                        "title": "Introduction to Ethics",
                        "description": "Professional ethics and ethical decision-making in modern society.",
                    },
                ],
            )

            subprocess.run(
                [
                    sys.executable,
                    "ai_analysis.py",
                    "--input-courses",
                    str(input_csv),
                    "--output-dir",
                    str(out_dir),
                ],
                check=True,
            )

            raw_with_flags = out_dir / "nau_courses_with_flag.csv"
            unique_with_flags = out_dir / "nau_unique_courses_with_flag.csv"
            ai_subset = out_dir / "nau_courses_ai_subset.csv"

            self.assertTrue(raw_with_flags.exists())
            self.assertTrue(unique_with_flags.exists())
            self.assertTrue(ai_subset.exists())

            with raw_with_flags.open(newline="", encoding="utf-8") as f:
                raw_rows = list(csv.DictReader(f))
            with unique_with_flags.open(newline="", encoding="utf-8") as f:
                unique_rows = list(csv.DictReader(f))
            with ai_subset.open(newline="", encoding="utf-8") as f:
                ai_rows = list(csv.DictReader(f))

            # Raw keeps term-level rows; unique collapses by (prefix, number).
            self.assertEqual(len(raw_rows), 3)
            self.assertEqual(len(unique_rows), 2)
            self.assertEqual(len(ai_rows), 1)

            # Ensure both flags exist on the unique output.
            self.assertIn("is_ai_related", unique_rows[0])
            self.assertIn("is_ethics_related", unique_rows[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
