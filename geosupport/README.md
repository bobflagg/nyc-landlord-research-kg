# geosupport/

A thin HTTP wrapper around NYC DCP **Geosupport Desktop Edition 25b** (design note 0013). Adapted from the Watchline discovery project's sidecar; this is our own copy so the two projects deploy separately.

| Endpoint | Request | Response |
| --- | --- | --- |
| `GET /health` | | `{"release": "25b"}` |
| `POST /resolve` | `{"house_number", "street_name", "zip_code"` or `"borough"}` | Geosupport's raw response, verbatim. A non-`00` return code is data, so it is still HTTP 200 |
| `POST /resolve_batch` | `{"rows": [ ... ]}` | `{"results": [ ... ]}`, one raw response per row, in order |

All interpretation (return codes, BBL and BIN, similar street names, spelled-out ordinals, unit text) is in `etl/geosupport.py`, where it is tested.

```
docker build --platform=linux/amd64 -t nyclr-geosupport geosupport/
docker run -d --platform=linux/amd64 -p 8081:8080 --name nyclr-geosupport nyclr-geosupport
```

`RELEASE`, `MAJOR` and `MINOR` in the `Dockerfile` must match `GEOSUPPORT_RELEASE` (default `25b`). The client checks `/health` and fails on a mismatch.
