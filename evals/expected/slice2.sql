-- Queries behind evals/expected/slice2.json, run read-only on the justfixwow database by derive_slice2.py.
-- %(bbls)s = the seven anchor BBLs (A-G); %(snap)s = 2026-05-29; %(today)s = the day it was run; %(deeds)s = the deed-family codes.

-- Q15 violation counts by class and status
select bbl, class, violationstatus, count(*) as n, min(inspectiondate) as oldest_inspection, max(inspectiondate) as latest_inspection,
       count(*) filter (where inspectiondate > %(snap)s) as inspected_after_snapshot
from hpd_violations where bbl = any(%(bbls)s) group by bbl, class, violationstatus order by bbl, class, violationstatus;

-- Q15 five oldest open violations
select bbl, violationid, class, inspectiondate, currentstatus from (
  select *, row_number() over (partition by bbl order by inspectiondate, violationid) as rn
  from hpd_violations where bbl = any(%(bbls)s) and violationstatus = 'Open' and inspectiondate is not null) x where rn <= 5 order by bbl, rn;

-- Q15/Q17/Q27 lot facts
select bbl, unitsres, unitstotal, yearbuilt, bldgclass from pluto_latest where bbl = any(%(bbls)s) order by bbl;

-- Q17 registrations
select bbl, registrationid, lastregistrationdate, registrationenddate from hpd_registrations where bbl = any(%(bbls)s) order by bbl, registrationid;

-- Q17 latest deed (not a correction), latest version of each document
select distinct on (l.bbl) l.bbl, m.documentid, m.doctype, m.recordedfiled, m.docdate, m.docamount
from real_property_legals l join (select distinct on (documentid) * from real_property_master order by documentid, modifieddate desc) m on m.documentid = l.documentid
where l.bbl = any(%(bbls)s) and m.doctype = any(%(deeds)s) and m.doctype <> 'DEED COR' and m.recordedfiled is not null
order by l.bbl, m.recordedfiled desc, m.documentid;

-- Q27 problems by type and status (all years)
select bbl, extract(year from receiveddate)::int as year, type, problemstatus,
       count(*) filter (where not problemduplicateflag) as problems, count(*) filter (where problemduplicateflag) as duplicates,
       count(distinct complaintid) filter (where not problemduplicateflag) as complaints, max(receiveddate) filter (where not problemduplicateflag) as latest
from hpd_complaints_and_problems where bbl = any(%(bbls)s) and receiveddate <= %(today)s group by bbl, year, type, problemstatus order by bbl, year, type, problemstatus;

-- Q27 problems by major category (all years)
select bbl, extract(year from receiveddate)::int as year, majorcategory, count(*) filter (where not problemduplicateflag) as problems
from hpd_complaints_and_problems where bbl = any(%(bbls)s) and receiveddate <= %(today)s group by bbl, year, majorcategory order by bbl, year, majorcategory;

-- Q28 litigation cases
select bbl, litigationid, casetype, caseopendate, casestatus, findingofharassment, respondent from hpd_litigations where bbl = any(%(bbls)s) order by bbl, litigationid;
