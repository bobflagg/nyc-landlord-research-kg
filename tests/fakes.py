from etl.geosupport import Outcome, Result, clean


class FakeGeo:
    """Stands in for the sidecar with a few invented addresses, so tests need no Docker."""

    TABLE = {
        "1 EXAMPLE STREET": Result(Outcome.RESOLVED, bbl="3000010001", bin="3000001", street="EXAMPLE STREET"),
        "3 EXAMPLE STREET": Result(Outcome.RESOLVED, bbl="3000010002", bin="3000002", street="EXAMPLE STREET"),
        "7 EXAMPLE STREET": Result(Outcome.RESOLVED, bbl="3999999999", bin=None, street="EXAMPLE STREET"),  # lot not in the graph
        "5 EXAMPLE STREET": Result(Outcome.NO_TAX_LOT, street="EXAMPLE STREET"),
        "9 EXAMPLR STREET": Result(Outcome.STREET_AMBIGUOUS, candidates=("EXAMPLE STREET", "EXAMPLER PLACE"), candidate_total=2),
    }

    def __init__(self, down: bool = False):
        self.down = down

    def resolve(self, house, street, zip5=None, borough=None):
        house, street, _ = clean(house, street)
        key = f"{house} {street}".upper()
        if self.down:
            return Result(Outcome.UNAVAILABLE, message="down", typed=key), [key]
        r = self.TABLE.get(key, Result(Outcome.STREET_NOT_RECOGNIZED, message="NOT RECOGNIZED"))
        return Result(**{**r.__dict__, "typed": key}), [key]
