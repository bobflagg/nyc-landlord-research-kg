"""Stream source rows from the justfixwow PostgreSQL. Read-only: the session is set read-only and nothing here writes.

Needs JUSTFIX_DATABASE_URL in .env (the database behind the postgres-justfix MCP server, port 5434).
Each reader yields dicts and streams through a server-side cursor, so the citywide tables never sit in memory.
"""
import os
from datetime import date
from typing import Iterator

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from etl.config import ROOT

PLUTO = """select bbl, address, zipcode, bldgclass, unitsres, unitstotal, numbldgs, yearbuilt, assesstot, ownername, cd
           from pluto_latest {where} order by bbl"""
REGISTRATIONS = """select registrationid, buildingid, bin, bbl, housenumber, streetname, zip, lastregistrationdate, registrationenddate
                   from hpd_registrations {where} order by registrationid"""
CONTACTS = """select c.registrationcontactid, c.registrationid, c.type, c.contactdescription, c.corporationname, c.title,
                     c.firstname, c.middleinitial, c.lastname, c.businesshousenumber, c.businessstreetname,
                     c.businessapartment, c.businesscity, c.businessstate, c.businesszip
              from hpd_contacts c {join} order by c.registrationid, c.registrationcontactid"""


def connect() -> psycopg.Connection:
    load_dotenv(ROOT / ".env")
    url = os.environ.get("JUSTFIX_DATABASE_URL")
    if not url:
        raise SystemExit("set JUSTFIX_DATABASE_URL in .env (read-only justfixwow database, port 5434)")
    return psycopg.connect(url, row_factory=dict_row, options="-c default_transaction_read_only=on")


def _stream(conn, name: str, sql: str, params: tuple = ()) -> Iterator[dict]:
    with conn.cursor(name=name) as cur:
        cur.itersize = 5000
        cur.execute(sql, params)
        yield from cur


def pluto(conn, community_district: int | None = None) -> Iterator[dict]:
    where, params = ("where cd = %s", (community_district,)) if community_district else ("", ())
    return _stream(conn, "pluto", PLUTO.format(where=where), params)


def registrations(conn, community_district: int | None = None) -> Iterator[dict]:
    where, params = (("where bbl in (select bbl from pluto_latest where cd = %s)", (community_district,))
                     if community_district else ("", ()))
    return _stream(conn, "registrations", REGISTRATIONS.format(where=where), params)


def contacts(conn, community_district: int | None = None) -> Iterator[dict]:
    join, params = (("join hpd_registrations r on r.registrationid = c.registrationid "
                     "where r.bbl in (select bbl from pluto_latest where cd = %s)", (community_district,))
                    if community_district else ("", ()))
    return _stream(conn, "contacts", CONTACTS.format(join=join), params)


def conflicted_bins(conn) -> frozenset:
    """Real BINs that HPD registers on more than one lot. Citywide even for a district run, so the answer does not
    depend on the district chosen (note 0014)."""
    with conn.cursor() as cur:
        cur.execute("""select bin from hpd_registrations where bin ~ '^[0-9]{7}$' and bin !~ '^[1-5]0{6}$'
                       group by bin having count(distinct bbl) > 1""")
        return frozenset(r["bin"] for r in cur)


MASTER = """select distinct on (m.documentid) m.documentid, m.crfn, m.doctype, m.docdate, m.docamount, m.recordedfiled
            from real_property_master m
            where m.doctype = any(%s)
              and exists (select 1 from real_property_legals l where l.documentid = m.documentid and l.bbl in ({lots}))
            order by m.documentid, m.modifieddate desc"""  # the source repeats a document once per modification; keep the latest


def graph_lots(conn, community_district: int | None = None) -> frozenset:
    """BBLs the graph holds: PLUTO lots (one district, if asked) and, citywide, HPD-registered lots."""
    sql, params = ("select bbl from pluto_latest where cd = %s", (community_district,)) if community_district else (
        "select bbl from pluto_latest union select bbl from hpd_registrations", ())
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return frozenset(r["bbl"].strip() for r in cur)


def acris_documents(conn, codes: list[str], community_district: int | None = None) -> Iterator[dict]:
    """Latest version of each document of the given types that is on a graph lot, in document id order."""
    lots = ("select bbl from pluto_latest where cd = %s" if community_district
            else "select bbl from pluto_latest union select bbl from hpd_registrations")
    return _stream(conn, "acris_documents", MASTER.format(lots=lots), (codes, *((community_district,) if community_district else ())))


def acris_children(conn):
    """A function that returns the (parties, legals) of a list of document ids, by index lookup."""
    def fetch(ids: list[str]) -> tuple[list[dict], list[dict]]:
        with conn.cursor() as cur:
            cur.execute("select documentid, partytype, name, address1, address2, city, state, zip, country "
                        "from real_property_parties where documentid = any(%s)", (ids,))
            parties = cur.fetchall()
            cur.execute("select documentid, bbl from real_property_legals where documentid = any(%s)", (ids,))
            return parties, cur.fetchall()
    return fetch


DOS = """select dosid, currententityname, initialdosfilingdate, county, jurisdiction, entitytype, dosprocessname,
                dosprocessaddress1, dosprocessaddress2, dosprocesscity, dosprocessstate, dosprocesszip,
                ceoname, ceoaddress1, ceoaddress2, ceocity, ceostate, ceozip,
                registeredagentname, registeredagentaddress1, registeredagentaddress2, registeredagentcity,
                registeredagentstate, registeredagentzip,
                locationname, locationaddress1, locationaddress2, locationcity, locationstate, locationzip
         from dos_active_corporations order by dosid"""


def dos_entities(conn) -> Iterator[dict]:
    """Every active DOS entity, statewide, in DOS id order."""
    return _stream(conn, "dos_entities", DOS)


LITIGATION = """select litigationid, casetype, caseopendate, casestatus, openjudgement, findingofharassment, findingdate, penalty,
                       respondent, bbl, bin from hpd_litigations order by litigationid"""


def litigation(conn) -> Iterator[dict]:
    return _stream(conn, "litigation", LITIGATION)


def as_of(conn, table: str, column: str, not_after: date) -> date:
    """The latest value of `column` that is not after `not_after` (the build date): a date later than the build is a typing
    error or a sentinel, not data (note 0020, C4)."""
    with conn.cursor() as cur:
        cur.execute(f"select max({column}) as d from {table} where {column} <= %s", (not_after,))
        return cur.fetchone()["d"]


VIOLATIONS = """select violationid, registrationid, class, inspectiondate, novissueddate, currentstatus, currentstatusdate, violationstatus,
                       rentimpairing, bbl, bin from hpd_violations {where} order by violationid"""


def violations(conn, bbls: list[str] | None = None) -> Iterator[dict]:
    """HPD violations in violation id order. Apartment, story and the notice text are not selected (note 0020)."""
    if bbls is None:
        return _stream(conn, "violations", VIOLATIONS.format(where=""))
    with conn.cursor() as cur:
        cur.execute(VIOLATIONS.format(where="where bbl = any(%s)"), (bbls,))
        return iter(cur.fetchall())


COMPLAINT_GROUPS = """select bbl, bin, extract(year from receiveddate)::int as year, {col} as group_value, problemstatus,
                             count(*) filter (where not problemduplicateflag) as problems,
                             count(*) filter (where problemduplicateflag) as duplicates,
                             {complaints} as complaints,
                             max(receiveddate) filter (where not problemduplicateflag) as latest_received
                      from hpd_complaints_and_problems where receiveddate <= %s {more}
                      group by bbl, bin, year, group_value, problemstatus"""


def complaint_groups(conn, grouping: str, not_after: date, bbls: list[str] | None = None) -> Iterator[dict]:
    """HPD complaint problems aggregated in the database by building, year, type (or major category) and problem status, so the
    16M rows never reach Python and no apartment, unit, complainant or anonymity column is read (note 0020, C2). Problems received
    after `not_after` (the build date) are typing errors and are left out."""
    col, complaints = (("type", "count(distinct complaintid) filter (where not problemduplicateflag)") if grouping == "type"
                       else ("majorcategory", "null::int"))
    sql = COMPLAINT_GROUPS.format(col=col, complaints=complaints, more="and bbl = any(%s)" if bbls else "")
    if bbls:
        with conn.cursor() as cur:
            cur.execute(sql, (not_after, bbls))
            return iter(cur.fetchall())
    return _stream(conn, f"complaints_{grouping}", sql, (not_after,))
