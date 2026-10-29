"""Rules N1 and N2, the name relation, the mail-drop list as nodes, and the vocabularies of Slice 5 (design note 0026)."""
import pytest

from agent.tools.linkrules import name_relation
from agent.tools.addresses import _ordinal, _variants
from etl.maildrop import maildrop_nodes
from etl.names import n1, n2
from etl.validate import validate
from tests.scope import SCOPE
from etl.vocab import bor_term


def test_n2_is_n1_with_spaces_removed_and_nothing_else():
    assert n1("K S Turnpike L.L.C.") == "K S TURNPIKE LLC" and n2("K S Turnpike L.L.C.") == "KSTURNPIKELLC"
    assert n2("KS Turnpike LLC") == n2("K S TURNPIKE LLC") and n1("KS Turnpike LLC") != n1("K S TURNPIKE LLC")
    assert n2("Acme LLC") != n2("Acme II LLC") and n2("Holdings") != n2("Holding")      # nothing fuzzy


@pytest.mark.parametrize("a,b,rel", [("Acme L.L.C.", "ACME LLC", "normalization_match"), ("KS Turnpike LLC", "K S TURNPIKE LLC", "spacing_match"),
                                     ("Example Holdings LLC", "Example Holdings II LLC", "differs_by_one_token"), ("5413 PLAZA LLC", "702 Plaza LLC", "differs_by_one_token"),
                                     ("702 54 STREET LLC", "702 PLAZA LLC", "different"), ("Acme LLC", "Beta Corp", "different"), ("", "x", "unusable")])
def test_name_relation(a, b, rel):
    assert name_relation(a, b)["relation"] == rel


def test_a_numeral_difference_says_it_is_not_the_same_entity_on_the_names_alone():
    r = name_relation("Example Holdings LLC", "Example Holdings II LLC")
    assert r["token_kind"] == "a numeral" and "different name" in r["reading"] and "record other than the name" in r["reading"]


def test_a_street_number_is_tried_as_an_ordinal_too():
    assert _ordinal(61) == "61ST" and _ordinal(52) == "52ND" and _ordinal(13) == "13TH" and _ordinal(3) == "3RD"
    assert _variants("746", "61 Street", "11220") == ["746 61 ST 11220", "746 61ST ST 11220"]


def test_the_mail_drop_list_becomes_unreviewed_type_ii_nodes_keyed_with_the_zip():
    nodes = maildrop_nodes()
    assert len(nodes) == 121 and len({n["maildrop_key"] for n in nodes}) == 121     # the row without a ZIP is not loaded
    n = next(x for x in nodes if x["maildrop_key"] == "418 BROADWAY 12207")
    assert (n["kind"], n["reliability"], n["source_category"], n["review_status"], n["source"]) == ("registered_agent", "II", "project_derived", "unreviewed", "mail_drop_list")
    assert all(x["maildrop_key"].endswith(" " + x["zip5"]) for x in nodes)


def test_the_list_loads_and_validates(tx, schema):
    from etl.load import load_nodes
    nodes = maildrop_nodes()
    load_nodes(tx, schema, "MailDropAddress", nodes[:5])
    tx.run("MATCH (m:MailDropAddress) WHERE m.maildrop_key IN $k SET m:`" + SCOPE + "`", k=[n["maildrop_key"] for n in nodes[:5]]).consume()
    assert validate(tx, only=("MailDrop",), scope=SCOPE) == []
    tx.run("MATCH (m:MailDropAddress) WHERE m.maildrop_key = $k SET m.kind = 'bogus'", k=nodes[0]["maildrop_key"]).consume()
    assert validate(tx, only=("MailDrop",), scope=SCOPE)


def test_vocabularies_refuse_an_unknown_term():
    assert bor_term("deed-pattern", "paired_with_sale") and bor_term("affiliation-type", "lender") and bor_term("address-kind", "unknown")
    with pytest.raises(ValueError):
        bor_term("deed-pattern", "sham")
