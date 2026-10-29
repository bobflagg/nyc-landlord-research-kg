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
EXPECTED3 = json.loads((ROOT / "evals" / "expected" / "slice3.json").read_text())
EXPECTED4 = json.loads((ROOT / "evals" / "expected" / "slice4.json").read_text())
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
    return out + slice2_examples() + slice3_examples() + slice3_loan_and_history_examples() + slice4_examples()


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


def slice3_examples() -> list[dict]:
    """Q12 on the anchors, from evals/expected/slice3.json."""
    out = []
    for a, e in EXPECTED3["questions"]["Q12"].items():
        bbl = EXPECTED3["anchors"][a]["bbl"]
        q = f"How many times has lot {bbl} been transferred by deed since 2015, and which of those were for value?"
        tools = [{"name": "get_deed_history", "args": {"bbl": bbl, "since_year": 2015}}]
        recent = [t for t in e["timeline"] if t["recorded"] >= "2015-01-01"]
        forbid = ["to the current owner", "sold to the current"]
        if not recent:
            out.append(_ex("Q12", a, q, _ref(tools, any_of=[["no deed", "none", "no transfer"]], caveats=[["not 'no transfer", "does not mean", "not mean", "not necessarily", "in the graph", "earlier deed", "before 2015", "recorded before"]], forbid=forbid)))
            continue
        caveats = [["not a sale", "isn't a sale", "not a transfer for value", "not for value"]] if any(t["amount"] == 0 for t in recent) else [["only the deed", "deed family", "deed-family", "deed documents"]]
        out.append(_ex("Q12", a, q, _ref(tools, include=[t["document_id"] for t in recent][:6], caveats=caveats, forbid=forbid)))
    return out


def slice3_loan_and_history_examples() -> list[dict]:
    """Q13 and Q14 on the anchors, from evals/expected/slice3.json, slice2.json and slice1.json."""
    out, A3 = [], EXPECTED3["anchors"]
    outstanding = ["is still outstanding", "remains unpaid", "has been paid off", "was paid off", "is outstanding", "was paid in full", "has been repaid"]
    for a, e in EXPECTED3["questions"]["Q13"].items():
        bbl = A3[a]["bbl"]
        q = f"What mortgages, assignments and satisfactions are recorded against lot {bbl}, and is there a satisfaction for each mortgage?"
        tools = [{"name": "get_mortgage_history", "args": {"bbl": bbl}}]
        if not EXPECTED2["questions"]["Q17"][a]["registered"]:
            out.append(_ex("Q13", a, q, _ref(tools, any_of=[["no hpd registration", "registered lots", "not loaded", "not in the graph", "no mortgage-family", "no document"]],
                                              caveats=[["not 'no mortgage", "not mean", "does not mean", "says nothing", "not a claim", "not that none"]], forbid=outstanding)))
            continue
        mortgages = [t for t in e["timeline"] if t["doc_type"] in ("MTGE", "M&CON", "CORRM")]
        include = [t["document_id"] for t in mortgages][:3]
        out.append(_ex("Q13", a, q, _ref(tools, include=include, caveats=[["not proof", "does not show", "not necessarily", "cannot say", "doesn't show", "not evidence", "no proof", "does not say"], ["reel", "citation", "cites", "cited", "recorded reference"]],
                                         forbid=outstanding)))
    q15, q2 = EXPECTED2["questions"]["Q15"], EXPECTED["questions"]["Q2"]
    forbid = ["the responsible party", "is responsible for the violation", "was responsible for the violation", "responsible owner"]
    for a, e in EXPECTED3["questions"]["Q12"].items():
        bbl = A3[a]["bbl"]
        v = q15.get(a)
        if isinstance(v, dict) and v.get("oldest_open_ids"):
            vid, on = v["oldest_open_ids"][0], v["oldest_open_inspection_date"]
            q, tools = f"Who held title to the building and who was the registered owner when violation {vid} was issued?", [{"name": "get_title_and_registrant_on_date", "args": {"violation_id": vid}}]
        else:
            on = "2024-04-08"
            q, tools = f"Who held title to lot {bbl} and who was the registered owner on {on}?", [{"name": "get_title_and_registrant_on_date", "args": {"bbl": bbl, "date": on}}]
        upto = [t for t in e["timeline"] if t["recorded"] <= on]
        last = max((t["recorded"] for t in upto), default=None)
        holders = sorted({" ".join(g.split()) for t in upto if t["recorded"] == last for g in t["grantees"]}) if last else []
        regs = q2[a]
        owners = sorted({" ".join(r["registered_owner"].split()) for r in regs if r["last_registration_date"] <= on <= r["registration_end_date"]}) if not isinstance(regs, str) else []
        include = [on, *holders[:2], *owners[:1]]
        caveats = [["today's records", "current records", "records of the past", "not a finding", "not proof", "not shown to be responsible", "not necessarily responsible", "recorded date"]]
        any_of = [] if holders else [["no deed", "cannot attribute", "no title holder", "not supported"]]
        if not owners:
            any_of.append(["no registered owner", "no registration", "none in force", "not in force", "no registrant", "cannot attribute"])
        out.append(_ex("Q14", a, q, _ref(tools, include=[x for x in include if x], any_of=any_of, caveats=caveats, forbid=forbid)))
    return out


LEAD = ["lead", "not legal ownership", "not a determination", "not proof of ownership", "not ownership", "not a finding"]
LAYER_OVERREACH = ["this landlord owns", "the landlord owns", "owner of this portfolio", "owns all", "owned by one", "are owned by", "is owned by", "controls these", "hazardous"]
NOT_EVIDENCE = ["not evidence", "does not mean", "not proof", "not the same as", "does not show", "no evidence", "says nothing", "not a finding", "doesn't mean"]


def slice4_examples() -> list[dict]:
    """Q8, Q9, Q10, Q19, Q21 and Q26 on the anchors and on groups found in the BOR release, from evals/expected/slice4.json."""
    E, Q4 = EXPECTED4, EXPECTED4["questions"]
    bbl = {**{k: v["bbl"] for k, v in E["anchors"].items()}, **{k: v["bbl"] for k, v in E["cases"].items()}}
    run = E["run_id"]
    out = []
    for k in ("C", "D", "H2", "H5"):
        e = Q4["Q9"][k]
        out.append(_ex("Q9", k, f"How many lots, buildings and residential units are in the Owner Portfolio that includes lot {bbl[k]}, and is that the same as its Operational Network?",
                       _ref([{"name": "get_owner_portfolio", "args": {"bbl": bbl[k]}}], include=[e["group_id"], run, str(e["residential_units"])],
                            caveats=[LEAD, ["tax lot", "lots"], ["provisional", "gold"]], forbid=LAYER_OVERREACH)))
    for k in ("A", "F"):
        e = Q4["Q9"][k]
        words = ["no registration", "not registered", "no hpd registration"] if e["reason_code"] == "no_registration" else ["no linkage", "no accepted", "no qualifying", "no_linkage"]
        out.append(_ex("Q9", k, f"Which Owner Portfolio is lot {bbl[k]} in, and how many buildings does it hold?",
                       _ref([{"name": "get_owner_portfolio", "args": {"bbl": bbl[k]}}], any_of=[words], caveats=[NOT_EVIDENCE], forbid=LAYER_OVERREACH)))
    for k in ("C", "D", "H1", "H3"):
        e = Q4["Q8"][k]
        kind = ["louvain", "community"] if e["split"] == "louvain" else ["whole", "connected component", "component"]
        out.append(_ex("Q8", k, f"Which buildings are in the Operational Network of lot {bbl[k]}, what links connect them, and is it a whole connected component or a split community?",
                       _ref([{"name": "get_operational_network", "args": {"bbl": bbl[k]}}], include=[e["group_id"], run], any_of=[kind], caveats=[LEAD], forbid=LAYER_OVERREACH)))
    d = Q4["Q10"]["D"]["differences"]["only_in_operational_network"]["lots"]
    out.append(_ex("Q10", "D", f"The Owner Portfolio and the Operational Network of lot {bbl['D']} list different lots. Which lots differ and why?",
                   _ref([{"name": "compare_ownership_layers", "args": {"bbl": bbl["D"]}}], include=[x["bbl"] for x in d], any_of=[["address"]],
                        caveats=[["derived", "lead", "neither", "not the true"], NOT_EVIDENCE], forbid=LAYER_OVERREACH)))
    h1 = Q4["Q10"]["H1"]
    out.append(_ex("Q10", "H1", f"Does the Operational Network of lot {bbl['H1']} hold more than one Owner Portfolio? Name them.",
                   _ref([{"name": "compare_ownership_layers", "args": {"bbl": bbl["H1"]}}], include=[h1["operational_network"], *[p for p in h1["portfolios_in_the_network"] if p != "(none)"]],
                        caveats=[["derived", "lead", "neither", "not the true"]], forbid=LAYER_OVERREACH)))
    h2 = Q4["Q10"]["H2"]
    out.append(_ex("Q10", "H2", f"Does the Owner Portfolio of lot {bbl['H2']} span more than one Operational Network? Name them.",
                   _ref([{"name": "compare_ownership_layers", "args": {"bbl": bbl["H2"]}}], include=[h2["owner_portfolio"], *[n for n in h2["networks_in_the_portfolio"] if n != "(none)"]],
                        caveats=[["derived", "lead", "neither", "not the true"]], forbid=LAYER_OVERREACH)))
    for e in Q4["Q19"]:
        a, b = e["bbl_a"], e["bbl_b"]
        q = f"Why are lots {a} and {b} grouped together, or why not? Answer for both layers."
        tools = [{"name": "explain_why_grouped", "args": {"bbl_a": a, "bbl_b": b}}]
        include, any_of, caveats = [], [], [NOT_EVIDENCE if all(e[l]["verdict"] != "same_group" for l in ("owner_portfolio", "operational_network")) else LEAD]
        for lay in ("owner_portfolio", "operational_network"):
            v = e[lay]
            if v["verdict"] == "same_group":
                include.append(v["groups"][0])
            elif v["verdict"] == "different_groups":
                include += [g for g in v["groups"] if g]
        if e["a"] == "A":
            any_of.append(["no linkage", "no accepted", "no qualifying", "no_linkage"])
        out.append(_ex("Q19", f"{e['a']}-{e['b']}", q, _ref(tools, include=include, any_of=any_of, caveats=caveats, forbid=LAYER_OVERREACH)))
    for k, lay in (("C", "owner_portfolio"), ("D", "operational_network")):
        e = Q4["Q21"][k][lay]
        out.append(_ex("Q21", k, f"Within the {lay.replace('_', ' ').title()} of lot {bbl[k]}, which lots have the most open violations per residential unit, and how concentrated are they?",
                       _ref([{"name": "rank_violations_in_group", "args": {"bbl": bbl[k], "layer": lay}}], include=[e["top_lots_by_open_per_unit"][0]],
                            caveats=[["class a", "by class", "class b"], ["part of all", "partial", "about a fifth", "does not show", "not shown"]], forbid=LAYER_OVERREACH)))
    for k in ("D", "F", "M", "V"):
        e = Q4["Q26"][k]
        any_of = []
        if k == "D":
            any_of.append(["department of state", "dos"])
        if k == "F":
            any_of.append(["no registration", "no hpd registration", "not registered"])
        if k == "M":
            any_of.append(["masked", "aggregator", "shared by"])
        if k == "V":
            any_of.append(["veto", "first-name", "first name"])
        out.append(_ex("Q26", k, f"For lot {bbl[k]}, which sources have no record and what does each absence mean?",
                       _ref([{"name": "explain_what_is_missing", "args": {"bbl": bbl[k]}}], any_of=any_of, caveats=[NOT_EVIDENCE], forbid=LAYER_OVERREACH + ["is exempt", "does not exist"])))
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
