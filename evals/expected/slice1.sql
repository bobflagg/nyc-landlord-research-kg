-- Queries behind evals/expected/slice1.json, run read-only on the justfixwow database (snapshot justfixwow-2026-05-29).
-- :bbls = the seven anchor BBLs of docs/competency-questions-detail.md (A-G).

-- Q1: lot facts
select bbl, address, zipcode, bldgclass, unitsres, unitstotal, numbldgs, yearbuilt, assesstot, ownername, version
from pluto_latest where bbl in (:bbls) order by bbl;
-- Q1/Q2: registrations and buildings
select bbl, registrationid, bin, buildingid, housenumber, streetname, zip, lastregistrationdate, registrationenddate
from hpd_registrations where bbl in (:bbls) order by bbl, registrationid;
-- Q2/Q4: contacts (person names are not copied into the expected file; registrationcontactid identifies them)
select r.bbl, c.registrationcontactid, c.registrationid, c.type, c.contactdescription, c.corporationname, c.title,
       (c.firstname is not null and c.firstname <> '') as has_person_name,
       c.businesshousenumber, c.businessstreetname, c.businesszip
from hpd_contacts c join hpd_registrations r on r.registrationid = c.registrationid
where r.bbl in (:bbls) order by r.bbl, c.registrationid, c.type;
-- Q3: deeds on each lot, then the parties of the most recent ones (partytype 1 grantor, 2 grantee)
select l.bbl, m.documentid, m.doctype, m.docdate, m.docamount, m.recordedfiled
from real_property_legals l join real_property_master m on m.documentid = l.documentid
where l.bbl in (:bbls) and m.doctype ilike 'DEED%' order by l.bbl, m.docdate desc nulls last;
select documentid, partytype, name, address1, address2, city, state, zip from real_property_parties
where documentid in (:most_recent_deed_ids) order by documentid, partytype, name;
-- Q5: DOS record by exact normalized name (rule N1)
select dosid, currententityname, initialdosfilingdate, entitytype, jurisdiction, dosprocessname, dosprocessaddress1,
       dosprocesscity, dosprocesszip, registeredagentname
from dos_active_corporations
where trim(regexp_replace(regexp_replace(upper(currententityname), '[^A-Z0-9 ]', '', 'g'), '\s+', ' ', 'g')) in (:n1_names);
-- Q24: every ACRIS document naming the entity, with its lots
select p.name, p.partytype, m.documentid, m.doctype, m.docdate, m.docamount, array_agg(distinct l.bbl) as bbls
from real_property_parties p join real_property_master m on m.documentid = p.documentid
left join real_property_legals l on l.documentid = p.documentid
where upper(p.name) ~ '^5413 +PLAZA' group by 1, 2, 3, 4, 5, 6 order by m.docdate;
