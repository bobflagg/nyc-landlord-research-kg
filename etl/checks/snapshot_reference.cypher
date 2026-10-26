// Every fact's snapshot_id must name a Snapshot in the catalog (notes 0005, 0008).
// SHACL cannot express this. Read-only; any returned row is a violation and fails the build.
MATCH (n)
WHERE n.snapshot_id IS NOT NULL AND NOT n:Snapshot
  AND NOT EXISTS { MATCH (s:Snapshot {snapshot_id: n.snapshot_id}) }
RETURN 'node' AS kind, labels(n) AS labels, n.snapshot_id AS snapshot_id, elementId(n) AS element
UNION ALL
MATCH ()-[r]->()
WHERE r.snapshot_id IS NOT NULL
  AND NOT EXISTS { MATCH (s:Snapshot {snapshot_id: r.snapshot_id}) }
RETURN 'relationship' AS kind, [type(r)] AS labels, r.snapshot_id AS snapshot_id, elementId(r) AS element
