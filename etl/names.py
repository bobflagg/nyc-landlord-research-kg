"""Name comparison rule N1 (design note 0006): uppercase, delete punctuation, collapse whitespace.
Names are compared exactly after this; nothing fuzzy (design note 0009)."""
import re


def n1(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9\s]", "", name.upper())).strip()


def n2(name: str) -> str:
    """Rule N2 (design note 0026, P3): N1 with all spaces removed, so 'KS TURNPIKE' and 'K S TURNPIKE' agree. Derived at query time, stored nowhere;
    nothing else is relaxed (no fuzzy or phonetic matching)."""
    return n1(name).replace(" ", "")
