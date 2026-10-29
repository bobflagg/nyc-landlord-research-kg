-- Queries behind evals/expected/slice4.json, run read-only on the justfixwow database by derive_slice4.py.
-- %(bbls)s = the lots of the groups of the cases. Group facts come from the BOR release CSVs, not from SQL.

-- lot facts
select bbl, address, bldgclass, unitsres from pluto_latest where bbl = any(%(bbls)s) order by bbl;

-- registrations (buildings by BIN)
select bbl, registrationid, bin from hpd_registrations where bbl = any(%(bbls)s) order by bbl, registrationid;

-- open violations by class
select bbl, class, count(*) as n from hpd_violations where bbl = any(%(bbls)s) and violationstatus = 'Open' group by bbl, class order by bbl, class;

-- all violations rows
select bbl, count(*) as n from hpd_violations where bbl = any(%(bbls)s) group by bbl;

-- litigation cases
select bbl, count(*) as n from hpd_litigations where bbl = any(%(bbls)s) group by bbl;

-- complaint problem rows
select bbl, count(*) as n from hpd_complaints_and_problems where bbl = any(%(bbls)s) group by bbl;
