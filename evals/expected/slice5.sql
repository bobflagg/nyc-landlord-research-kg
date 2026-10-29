-- Queries behind evals/expected/slice5.json, run read-only on the justfixwow database by derive_slice5.py.

-- contacts at an address
select * from hpd_contacts where businesshousenumber = %(house)s and businesszip like %(zip)s;

-- DOS entities by name
select dosid, currententityname, initialdosfilingdate from dos_active_corporations where upper(currententityname) like any(%(patterns)s);

-- mortgage-family parties of documents
select documentid, partytype, name from real_property_parties where documentid = any(%(ids)s);

-- registrations of an agent
select distinct r.registrationid, r.bbl, c.corporationname from hpd_contacts c join hpd_registrations r on r.registrationid = c.registrationid where c.type = 'Agent' and upper(c.corporationname) like %(pattern)s;

-- units of lots
select bbl, unitsres from pluto_latest where bbl = any(%(bbls)s);
