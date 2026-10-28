"""The Slice 1 and Slice 2 evaluation dataset, derived from the expected answers (evals/expected/slice1.json and slice2.json) so there is one source.

Each example: inputs {question}, outputs (the reference) and metadata. The reference is what a correct answer must
contain and must not contain, not a model answer: expected tools, facts, caveat phrases (any one of a group), and
forbidden claims. Q1 is covered by tests/test_q1_agent.py and tests/test_geosupport_live.py (it needs the Geosupport
sidecar); everything here runs on the graph alone. Design notes 0009, 0012 and 0017."""
import json
import uuid
from datetime import datetime, timezone

from etl.config import ROOT

EXPECTED = json.loads((ROOT / "evals" / "expected" / "slice1.json").read_text())
EXPECTED2 = json.loads((ROOT / "evals" / "expected" / "slice2.json").read_text())
Q, ANCHORS, SNAPSHOT = EXPECTED["questions"], EXPECTED["anchors"], EXPECTED["snapshot_id"]
SNAPSHOT_DATE = SNAPSHOT.split("-", 1)[1]            # 2026-05-29
OVERREACH = [" owns the ", " owns this ", " owned by", "is the owner of", "proves ownership", "confirmed owner", "controls the building"]
NO_RECORD = ["no record", "no dos record", "no match", "did not find", "not found", "no active"]
NOT_EXIST = ["not mean", "does not exist", "doesn't mean", "not that the entity", "not proof", "not the same as", "not necessarily", "no evidence that"]   # no record is not 'does not exist'


def _ref(tools, include=(), any_of=(), caveats=(), forbid=()) -> dict:
    return {"expected_tools": list(tools), "must_include": list(include), "must_include_any": [list(g) for g in any_of],
            "caveat_groups": [list(g) for g in caveats], "must_not_include": [*OVERREACH, *forbid]}


def _ex(qid, anchor, question, ref) -> dict:
    return {"inputs": {"question": question}, "outputs": ref, "metadata": {"question_id": qid, "anchor": anchor}}


def _names(expected_contacts, *types) -> list[str]:
    return [c["person_name"] or c["organization_name"] for c in expected_contacts if c["type"] in types]


def build_examples() -> list[dict]:
    out = []
    for a, regs in Q["Q2"].items():
        bbl = ANCHORS[a]["bbl"]
        q = f"Who is the HPD registered owner of lot {bbl} and when does the registration period end?"
        tools = [{"name": "get_hpd_registrations", "args": {"bbl": bbl}}]
        if isinstance(regs, str):
            out.append(_ex("Q2", a, q, _ref(tools, any_of=[["no hpd registration", "no registration", "not registered", "none", "no hpd", "no registered owner", "not in the snapshot"]])))
            continue
        out.append(_ex("Q2", a, q, _ref(tools, include=[SNAPSHOT_DATE, *[r["registration_id"] for r in regs], *[r["registration_end_date"] for r in regs],
                                                          *[r["registered_owner"] for r in regs]], caveats=[["title"]])))
    for a, e in Q["Q3"].items():
        bbl = ANCHORS[a]["bbl"]
        q = f"For lot {bbl}, who is the grantee on the most recent deed, and does that name match the HPD owner?"
        names = [g["grantee"] for g in e["grantees"]]
        agreements = {c["name_agreement"] for g in e["grantees"] if not isinstance(g["vs_hpd"], str) for c in g["vs_hpd"]}
        words = {"exact_normalized": ["exact", "same name", "match"], "different": ["different", "does not match", "not match", "differs"],
                 "not_comparable": ["not comparable", "individual", "not compared"]}
        any_of = [sorted({w for ag in agreements for w in words[ag]})] if agreements else [["no hpd registration", "no registration", "not registered", "no hpd owner", "no registered owner", "no hpd record", "no hpd"]]
        caveats = [["lead", "not proof", "does not mean", "not a finding"]] if "exact_normalized" in agreements else []
        out.append(_ex("Q3", a, q, _ref([{"name": "compare_deed_grantee_with_hpd_owner", "args": {"bbl": bbl}}],
                                         include=[d["document_id"] for d in e["deeds"]] + names, any_of=any_of, caveats=caveats)))
    for a, regs in Q["Q4"].items():
        bbl = ANCHORS[a]["bbl"]
        q = f"Who is the managing agent, the head officer and the site manager listed for lot {bbl}?"
        tools = [{"name": "get_hpd_contacts", "args": {"bbl": bbl}}]
        if isinstance(regs, str):
            out.append(_ex("Q4", a, q, _ref(tools, any_of=[["no hpd registration", "no registration", "not registered", "none", "no hpd", "no contacts", "not in the snapshot"]])))
            continue
        people = [n for contacts in regs.values() for n in _names(contacts, "Agent", "HeadOfficer", "SiteManager") if n]
        out.append(_ex("Q4", a, q, _ref(tools, include=sorted(set(people)), caveats=[["not ownership", "management relationship", "management"]])))
    dos = [("A", "5413 PLAZA LLC", Q["Q5"]["A"]["record"]), ("B", "702 Plaza LLC", Q["Q5"]["B"]["record"]),
           ("D", "SUNSET PARK OWNER I LLC", Q["Q5"]["D"]["other"]), ("E", "234 54TH ST LLC", Q["Q5"]["E"]["deed_grantee_record"]),
           ("F", "259 22ND STREET LLC", Q["Q5"]["F"]["record"]), ("G", "K S TURNPIKE LLC", Q["Q5"]["G"]["record"]),
           ("C", "438 52ND ST OWNERS CORP", Q["Q5"]["C"]["record"])]
    for a, name, rec in dos:
        out.append(_ex("Q5", a, f"What does the New York Department of State record say about {name}?",
                       _ref([{"name": "get_dos_record", "args": {"name": name}}], include=[rec["dos_id"], rec["initial_filing_date"]],
                            caveats=[["active"]])))
    for a, name in [("C", "438 52 ST OWNERS CORP"), ("D", "HP SUNSET PARK I HDFC INC."), ("G", "KS Turnpike LLC")]:   # the HPD spellings
        out.append(_ex("Q5", a, f"Is there a New York Department of State record for the owner {name}?",
                       _ref([{"name": "get_dos_record", "args": {"name": name}}], any_of=[NO_RECORD], caveats=[NOT_EXIST])))
    q24 = Q["Q24"]
    docs = [d["document_id"] for d in q24["acris_documents"]]
    out.append(_ex("Q24", "A", "I have a letter from 5413 PLAZA LLC. What do the records show for that name?",
                   _ref([{"name": "find_records_by_name", "args": {}}], include=[q24["dos"]["dos_id"], q24["hpd"][0]["registration_id"], *sorted(set(docs))],
                        caveats=[["deed"], ["only", "not loaded", "not searched", "not included"]])))
    out.append(_ex("Q24", "G", "What do the records show for KS Turnpike LLC?",
                   _ref([{"name": "find_records_by_name", "args": {}}], include=["305188"],      # trying the other spelling is allowed if it is labelled a variant; the judge checks it is not joined
                        caveats=[["spelling", "different name", "variant"]])))
    out.append(_ex("Q24", "C", "Which lots does SAHIT HADZOVIC appear against in HPD registrations, and in which roles?",
                   _ref([{"name": "find_records_by_name", "args": {}}], include=["3008070024"],
                        any_of=[["managing agent", "agent"], ["head officer"]], caveats=[["lead", "same name", "not proof", "not a finding"]])))
    out.append(_ex("Q24", "none", "What do the records show for Zzyzx Holdings LLC?",
                   _ref([{"name": "find_records_by_name", "args": {}}], any_of=[NO_RECORD], caveats=[["variants", "normalized", "tried"]])))
    return out + slice2_examples()


NO_VIOLATION = ["no violation", "no hpd violation", "none in the data", "no open", "does not hold any"]
NO_COMPLAINT = ["no complaint", "no hpd complaint", "none in the data", "no problem"]
NO_CASE = ["no case", "no hpd", "no housing court", "none in the data", "no litigation"]


def slice2_examples() -> list[dict]:
    """Q15, Q17, Q27 and Q28 on the anchors, from evals/expected/slice2.json. The data is newer than the snapshot date, so each
    answer must give its source's as-of date beside the snapshot."""
    Q2_, A2, ASOF = EXPECTED2["questions"], EXPECTED2["anchors"], EXPECTED2["as_of"]
    out = []
    for a, e in Q2_["Q15"].items():
        bbl = A2[a]["bbl"]
        q, tools = f"How many open HPD violations does lot {bbl} have, by class, and what is the oldest open one?", [{"name": "get_hpd_violations", "args": {"bbl": bbl}}]
        partial = [["part of all", "only part", "partial", "not all"]]
        if isinstance(e, str):
            out.append(_ex("Q15", a, q, _ref(tools, any_of=[NO_VIOLATION], caveats=[["does not show", "not show", "never had", "not mean"], *partial])))
            continue
        include = [ASOF["hpd_violations"], *e["oldest_open_ids"][:1], *([e["oldest_open_inspection_date"]] if e["oldest_open_inspection_date"] else [])]
        any_of = [["class i", "class-i"]] if e["open_class_i"] else []
        out.append(_ex("Q15", a, q, _ref(tools, include=include, any_of=any_of, caveats=[["not a court", "inspector", "cited"], *partial])))
    for a, e in Q2_["Q17"].items():
        bbl = A2[a]["bbl"]
        q, tools = f"Is lot {bbl} registered with HPD, and is the registration current?", [{"name": "get_registration_status", "args": {"bbl": bbl}}]
        legal = ["required", "legally", "legal", "applicab"]
        if not e["registered"]:
            out.append(_ex("Q17", a, q, _ref(tools, any_of=[["no registration", "no hpd registration", "none", "not registered", "no registration is"]], caveats=[legal, ["legitimate reason", "new building", "recently"]],
                                              forbid=["failed to register", "illegally"])))
            continue
        any_of = [["ended", "lapsed", "expired", "no longer"]] if e["lapsed"] else [["current", "not lapsed", "has not ended", "not ended", "still in effect", "runs until", "ends on"]]
        include = [e["latest_registration_end_date"], e["registration_ids"][0]]
        out.append(_ex("Q17", a, q, _ref(tools, include=include, any_of=any_of, caveats=[legal], forbid=["failed to register", "illegally"])))
    for a, e in Q2_["Q27"].items():
        bbl = A2[a]["bbl"]
        w = e["since_2022"]
        q, tools = f"Since 2022, how many HPD complaints has lot {bbl} had, by type, and are any still open?", [{"name": "get_hpd_complaints", "args": {"bbl": bbl, "since_year": 2022}}]
        if isinstance(w, str):
            out.append(_ex("Q27", a, q, _ref(tools, any_of=[NO_COMPLAINT])))
            continue
        out.append(_ex("Q27", a, q, _ref(tools, include=[ASOF["hpd_complaints"], w["latest_received"], str(w["problems"])],
                                         caveats=[["not a finding", "a report", "reports"], ["duplicate"]])))
    for a, e in Q2_["Q28"].items():
        bbl = A2[a]["bbl"]
        q, tools = f"Has HPD brought any Housing Court cases against the owners of lot {bbl}?", [{"name": "get_hpd_litigation", "args": {"bbl": bbl}}]
        if isinstance(e, str):
            out.append(_ex("Q28", a, q, _ref(tools, any_of=[NO_CASE], caveats=[["does not mean", "not mean", "not necessarily", "only hpd", "dataset only", "litigation data", "litigation dataset", "does not show"]])))
            continue
        out.append(_ex("Q28", a, q, _ref(tools, include=[ASOF["hpd_litigation"], *[c["litigation_id"] for c in e]], caveats=[["not an eviction", "not a finding", "eviction"]])))
    return out


def as_examples(examples: list[dict]) -> list:
    """LangSmith Example objects, so the examples can be evaluated locally without a dataset in LangSmith."""
    from langsmith.schemas import Example
    now, ds = datetime.now(timezone.utc), uuid.uuid4()
    return [Example(id=uuid.uuid5(uuid.NAMESPACE_URL, e["inputs"]["question"]), dataset_id=ds, created_at=now, modified_at=now,
                    inputs=e["inputs"], outputs=e["outputs"], metadata=e["metadata"]) for e in examples]


if __name__ == "__main__":
    ex = build_examples()
    print(len(ex), "examples")
    for e in ex:
        print(e["metadata"], e["inputs"]["question"][:90])
