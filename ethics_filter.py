#!/usr/bin/env python3
"""
Ethics matching utilities.

This module provides a conservative ethics matcher designed to reduce false
positives from casual mentions of ethics in course descriptions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


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
    def build(cls, include_description: bool = True) -> "EthicsMatcher":
        description_patterns: tuple[re.Pattern[str], ...]
        if include_description:
            description_patterns = tuple(
                re.compile(pattern, re.IGNORECASE)
                for pattern in DESCRIPTION_PATTERNS
            )
        else:
            description_patterns = ()

        return cls(
            title_patterns=tuple(
                re.compile(pattern, re.IGNORECASE) for pattern in TITLE_PATTERNS
            ),
            description_patterns=description_patterns,
        )

    def is_match(self, title: str | None, description: str | None) -> bool:
        title_text = title or ""
        description_text = description or ""
        if any(p.search(title_text) for p in self.title_patterns):
            return True
        if not self.description_patterns:
            return False
        return any(p.search(description_text) for p in self.description_patterns)
