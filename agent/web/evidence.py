"""Session evidence (design note 0028, W2): the typed objects the Slice 6 tools return. Never written to the graph.

An EvidenceItem carries the fields of the Q16 contract. Coded values are terms of the vocabularies evidence-relation, match-basis, extraction-method and lead-reason
(checked on construction, so a typo or a new term is an error). A reported claim is reliability I only as to the fact that it was published (note 0002)."""
import time
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field, field_validator

from etl.vocab import bor_term

REPORTED = ("published_reporting", "web_content")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class EvidenceItem(BaseModel):
    item_id: str
    publisher_or_body: str
    published: date | None = None
    retrieved_at: str
    cached: bool = False
    url: str | None = None
    document_id: str | None = None
    page: str | None = None
    quote: str
    claim: str | None = None                 # one line saying what the quote claims, when read by a model
    extraction_method: str
    source_category: str
    review_status: str = "unreviewed"
    reliability: str = "I"                   # as to the fact of publication, or of the registry record
    match_basis: str
    matched_text: str | None = None          # the name or address that matched
    relation_to_records: str
    relation_note: str | None = None
    confidence: str = "normal"               # normal or low
    flags: list[str] = Field(default_factory=list)

    @field_validator("extraction_method")
    @classmethod
    def _method(cls, v):
        return bor_term("extraction-method", v)

    @field_validator("match_basis")
    @classmethod
    def _basis(cls, v):
        return bor_term("match-basis", v)

    @field_validator("relation_to_records")
    @classmethod
    def _rel(cls, v):
        return bor_term("evidence-relation", v)

    @field_validator("source_category")
    @classmethod
    def _cat(cls, v):
        return bor_term("source-category", v)

    @field_validator("review_status")
    @classmethod
    def _rs(cls, v):
        if v not in ("unreviewed", "contested"):
            raise ValueError("a session finding is unreviewed or contested")
        return v

    def out(self) -> dict:
        d = self.model_dump(mode="json")
        return {k: v for k, v in d.items() if v not in (None, [], "")}


class Lead(BaseModel):
    """A step that did not become a finding, with the reason."""
    step: str
    reason: str
    detail: str
    url: str | None = None
    retrieved_at: str | None = None

    @field_validator("reason")
    @classmethod
    def _reason(cls, v):
        return bor_term("lead-reason", v)

    def out(self) -> dict:
        return {k: v for k, v in self.model_dump(mode="json").items() if v is not None}


class BudgetExhausted(Exception):
    pass


class Budget:
    """Step and time limits (Q16 input). 'Nothing found' means nothing found within this budget, and the result says so."""

    def __init__(self, searches: int = 5, fetches: int = 10, seconds: float = 90.0):
        self.max_searches, self.max_fetches, self.seconds = searches, fetches, seconds
        self.searches = self.fetches = 0
        self.t0 = time.monotonic()

    def use(self, kind: str) -> None:
        if time.monotonic() - self.t0 > self.seconds:
            raise BudgetExhausted(f"time limit of {self.seconds:.0f} seconds reached")
        if kind == "search":
            if self.searches >= self.max_searches:
                raise BudgetExhausted(f"search limit of {self.max_searches} reached")
            self.searches += 1
        else:
            if self.fetches >= self.max_fetches:
                raise BudgetExhausted(f"fetch limit of {self.max_fetches} reached")
            self.fetches += 1

    def report(self) -> dict:
        return {"searches_used": self.searches, "searches_allowed": self.max_searches, "fetches_used": self.fetches, "fetches_allowed": self.max_fetches,
                "seconds_used": round(time.monotonic() - self.t0, 1), "seconds_allowed": self.seconds}
