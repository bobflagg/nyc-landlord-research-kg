"""Name comparison rule N1 (design note 0006): uppercase, delete punctuation, collapse whitespace.
Names are compared exactly after this; nothing fuzzy (design note 0009)."""
import re


def n1(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9\s]", "", name.upper())).strip()
