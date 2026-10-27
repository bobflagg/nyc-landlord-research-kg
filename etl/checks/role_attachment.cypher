// A role is on exactly one of a building or a lot (design note 0010); an ACRIS role is in a document instead (note 0015). Not expressible in the compiled SHACL:
// shacl2cypher treats relationship paths inside sh:xone as properties. Read-only; any returned row fails the build.
MATCH (r:Role)
WHERE NOT r:AcrisRole  // an ACRIS role is in a document (AcrisRoleShape), not on a building or lot
WITH r, COUNT { (r)-[:ON_BUILDING]->() } AS buildings, COUNT { (r)-[:ON_LOT]->() } AS lots
WHERE buildings + lots <> 1
RETURN r.role_id AS role_id, buildings, lots
