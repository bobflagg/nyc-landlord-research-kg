"""Geosupport sidecar: a pass-through HTTP service (design note 0013).

GET /health -> {"release": ...}
POST /resolve {house_number, street_name, borough | zip_code} -> Geosupport's raw response, verbatim.
POST /resolve_batch {"rows": [{...}, ...]} -> {"results": [...]} one raw response per row, in order.

All interpretation of the response lives in the client (etl/geosupport.py), in version control and tested.
A non-'00' return code is data, not an error, so it returns 200 with the raw payload.
"""
import os

from flask import Flask, jsonify, request
from geosupport import Geosupport, GeosupportError
from waitress import serve

RELEASE = os.environ.get("RELEASE", "25b")
app = Flask(__name__)
_geosupport = Geosupport()  # fails at start if the files are missing, rather than answering "not found" for everything


def _one(body: dict) -> dict:
    args = {"house_number": body.get("house_number"), "street_name": body.get("street_name")}
    if body.get("zip_code"):
        args["zip_code"] = body["zip_code"]
    else:
        args["borough"] = body.get("borough")
    try:
        return _geosupport.address(**args)
    except GeosupportError as exc:
        return exc.result


@app.get("/health")
def health():
    return jsonify({"release": RELEASE})


@app.post("/resolve")
def resolve():
    return jsonify(_one(request.get_json(silent=True) or {}))


@app.post("/resolve_batch")
def resolve_batch():
    rows = (request.get_json(silent=True) or {}).get("rows", [])
    return jsonify({"results": [_one(r) for r in rows]})


if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=8080)
