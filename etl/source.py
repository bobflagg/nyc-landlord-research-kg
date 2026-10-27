"""Stream source rows from the justfixwow PostgreSQL. Read-only: the session is set read-only and nothing here writes.

Needs JUSTFIX_DATABASE_URL in .env (the database behind the postgres-justfix MCP server, port 5434).
Each reader yields dicts and streams through a server-side cursor, so the citywide tables never sit in memory.
"""
import os
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
