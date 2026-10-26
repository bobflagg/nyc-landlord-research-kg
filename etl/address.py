"""Address comparison key, rule A2 (design note 0006): uppercase, delete punctuation, collapse whitespace,
map street-suffix spellings to one form. House number, street and 5-digit zip make the key. Unit and floor
text are not part of it. Ordinal spellings (54TH vs 54) are not mapped, so a miss reports the key it tried."""
import re

SUFFIX = {
    "STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "BOULEVARD": "BLVD", "PLACE": "PL", "DRIVE": "DR",
    "COURT": "CT", "LANE": "LN", "TERRACE": "TER", "PARKWAY": "PKWY", "HIGHWAY": "HWY", "SQUARE": "SQ",
}


def a2_key(house_number: str, street: str, zip5: str) -> str:
    def clean(s: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", s.upper())).strip()

    words = [SUFFIX.get(w, w) for w in clean(street).split()]
    zip5 = re.sub(r"\D", "", zip5)[:5]
    return " ".join([clean(house_number), *words, zip5])
