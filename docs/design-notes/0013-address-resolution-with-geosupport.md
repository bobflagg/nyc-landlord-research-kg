# 0013: Resolve typed addresses with Geosupport

Date: 2026-10-26

Status: **accepted 2026-10-26** (the choice of Geosupport and of more steps to raise recall was yours; the specifics below follow from the spike). Amends note 0006 (address rule A3 is adopted for typed-address resolution; A2 stays for stored strings), `specs/tech-stack.md`, `CLAUDE.md`, `README.md` and `.env.example`. Builds on notes 0006, 0010 and 0012.

## Decision

1. **A typed address resolves through NYC DCP Geosupport,** release 25b, served by a sidecar container in `geosupport/` (our own copy of the Watchline discovery project's sidecar; port 8081 so the two do not collide). It is the city's own standardizer, the source PLUTO and HPD derive from. Geosupport gives the BBL and the BIN of the address directly, so Q1 does not depend on how a string is spelled.
2. **The graph confirms what Geosupport returns.** The lot is looked up by BBL and its buildings by `ON_LOT`. Three outcomes are kept apart: found; **geocoded but absent** (the city resolves the address to a lot the graph does not hold); and not found with a reason.
3. **Steps taken to raise recall,** all in `etl/geosupport.py` and tested:
   - strip unit, floor and "rear" text before sending;
   - retry once with spelled-out ordinals as digits ("Fifty-fourth Street" to "54 Street");
   - accept a zip code or a borough in place of the other;
   - report every spelling tried;
   - on an unknown street, return the city's similar street names (capped at five, the total reported) and let the user choose, instead of guessing;
   - keep the outcomes distinct: no tax lot, house number out of range, street not recognized, invalid input, and **sidecar unavailable, which is never reported as "not found"**;
   - treat a placeholder BIN (`x000000`) as a lot with no building record, and keep the condominium billing BBL when there is one.
4. **Release pin.** `/health` reports the release and the client raises on a mismatch with `GEOSUPPORT_RELEASE`.
5. **A2 stays for stored strings.** Rule A2 (note 0006) still compares business addresses, the mail-drop list and HPD identity nodes. Moving those to Geosupport is not decided here (see Open).

## Evidence (spike, 2026-10-26)

- **198 HPD registrations** sampled deterministically (md5 of the registration id), each typed the HPD way with its zip:
  - rule A2 reaches the lot's PLUTO address key for **100 of 198 (51%)**;
  - Geosupport returns the lot's BBL for **197 of 198 (99.5%)** and its BIN for **195 of 198**. The one BBL difference was a lot whose Geosupport BIN is a placeholder (`4000000`).
- **Speed:** 198 addresses in 0.2 seconds in one batch call, under emulation on Apple Silicon. Geocoding every stored address at load is practical.
- **Anchors A to G:** every HPD and PLUTO spelling reaches the expected BBL and BIN, including 218 and 220 54th Street of lot D (`tests/test_geosupport_live.py`).
- **Typed variants that resolve:** `54 St`, `54th Street`, `7th Ave`, `Seventh Ave.`, `St Nicholas Ave` and `Saint Nicholas Avenue`, a unit suffix, a range (`218-224`), a borough in place of a zip, and a wrong zip inside the right borough.
- **Cases that need the client's help:** `Fifty-fourth Street` and `54 STREET APT 3B` fail raw and resolve after cleaning. `Seventh Avnue` returns similar streets, not a lot. `222 54 Street` is a real number with no tax lot. `0 54 Street` is out of range.

## Context

- Note 0006 chose A2 and deferred A3 (full standardization with Geosupport or libpostal). The expected-answers work (2026-10-26) showed A2 misses about half of HPD building addresses against PLUTO because it does not map ordinals.
- The Watchline discovery project already runs Geosupport this way (its decisions D9, D10 and D12). Its sidecar and client design are reused; the code is our own.

## Alternatives considered

- **Extend A2 with ordinal and spelled-number mapping only.** Cheap, but a hand-maintained subset of what the city already standardizes (aliases, ranges, hyphenated Queens numbers, St/Saint).
- **libpostal.** Parses well but does not know New York's street dictionary or lots.
- **Reuse the Watchline sidecar as it runs.** Couples two projects' deployments; a shared release pin is the only coupling worth keeping, and a copy keeps it explicit.
- **Fall back to A2 when the sidecar is down.** Would hide an outage as a smaller recall. The agent says the service is unavailable instead.

## Consequences

- **Dependency:** a Docker image of about 2 GB, `linux/amd64` under emulation on Apple Silicon. Tests that need it carry the `geosupport` marker and skip when it is not running; everything else uses a stub (`tests/fakes.py`).
- **Q1 tool** (`agent/tools/lookup.py`) now resolves through Geosupport and confirms in the graph. The Slice 0 sample lots are invented, so the agent test stubs the geocoder.
- **Geosupport is a local, deterministic canonicalizer, not a source of facts.** The BBL and BIN it returns are tagged by the graph's own PLUTO and HPD records, which carry the provenance. The answer states that the address service resolved the address.
- **Release drift:** Geosupport 25b and PLUTO 26v1 can disagree about a lot (a merged or renumbered lot). That is what "geocoded but absent" reports.
- **Expected answers:** `evals/expected/slice1.json` finding on ordinals now points here.

## Open

- **Business and party addresses** (HPD contact addresses, ACRIS parties, DOS) could also be geocoded at load, so "who else uses this address" compares the city's canonical address instead of an A2 string. It would raise recall for Q6, Q7 and Q18. It touches the HPD identity nodes of note 0006 and the mail-drop list, and BOR masks with its own normalizer, so the keys would need to stay compatible. Decide in Slice 5 with measured numbers.
- **Corner addresses and intersections** (Geosupport function 2) are not handled; the Q1 pending case "corner address" is open.
- **Out-of-city addresses** fail in Geosupport and fall back to A2 or no key.
- Whether to cache responses for the full load.
