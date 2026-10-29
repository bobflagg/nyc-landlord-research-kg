-- Queries behind evals/expected/slice3.json, run read-only on the justfixwow database by derive_slice3.py.
-- %(bbls)s = the seven anchor BBLs (A-G); %(deeds)s = the deed-family codes; %(doc_ids)s = the deeds found by the first query.

-- Q12 deeds on each lot (latest version of each document, corrections excluded)
select l.bbl, m.documentid, m.doctype, m.docdate, m.recordedfiled, m.docamount,
       (select array_agg(distinct l2.bbl order by l2.bbl) from real_property_legals l2 where l2.documentid = m.documentid) as lots
from real_property_legals l
join (select distinct on (documentid) * from real_property_master order by documentid, modifieddate desc) m on m.documentid = l.documentid
where l.bbl = any(%(bbls)s) and m.doctype = any(%(deeds)s) and m.doctype <> 'DEED COR'
order by l.bbl, m.recordedfiled, m.docdate, m.documentid;

-- Q12 corrections on each lot
select l.bbl, count(distinct m.documentid) as n from real_property_legals l join real_property_master m on m.documentid = l.documentid
where l.bbl = any(%(bbls)s) and m.doctype = 'DEED COR' group by l.bbl order by l.bbl;

-- Q12 parties of those deeds (party type 1 grantor, 2 grantee)
select p.documentid, p.partytype, p.name from real_property_parties p
where p.documentid = any(%(doc_ids)s) and p.partytype in ('1', '2') order by p.documentid, p.partytype, p.name;

-- Q13 mortgage-family documents on each lot (latest version of each document)
select l.bbl, m.documentid, m.crfn, m.doctype, m.docdate, m.recordedfiled, m.docamount
from real_property_legals l
join (select distinct on (documentid) * from real_property_master order by documentid, modifieddate desc) m on m.documentid = l.documentid
where l.bbl = any(%(bbls)s) and m.doctype = any(%(mortgage_codes)s) order by l.bbl, m.recordedfiled, m.docdate, m.documentid;

-- Q13 recorded references of those documents
select documentid, referencebycrfn, referencebydocid from real_property_references where documentid = any(%(doc_ids)s);

-- Q13 the documents those references cite by CRFN or document id (latest version), with the lots they are on
select m.documentid, m.crfn, m.doctype,
       (select array_agg(distinct l.bbl) from real_property_legals l where l.documentid = m.documentid) as lots
from (select distinct on (documentid) * from real_property_master where crfn = any(%(crfns)s) or documentid = any(%(docids)s) order by documentid, modifieddate desc) m;
