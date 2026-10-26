# Geosupport sidecar for this project (design note 0013). Adapted from the Watchline discovery
# project's sidecar (WatchlineNYC/sidecar), kept as our own copy so the two projects deploy separately.
#
# A thin HTTP wrapper around NYC DCP Geosupport Desktop Edition. python-geosupport needs the Linux
# binaries, so this image is linux/amd64 and runs under emulation on Apple Silicon.
#
#   docker build --platform=linux/amd64 -t nyclr-geosupport geosupport/
#   docker run -d --platform=linux/amd64 -p 8081:8080 --name nyclr-geosupport nyclr-geosupport
#
# RELEASE/MAJOR/MINOR is the release the loader and the agent both use; /health reports it and the
# client fails on a mismatch.
FROM python:3.10-slim

ENV RELEASE=25b
ENV MAJOR=25
ENV MINOR=2

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl unzip \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /geosupport
RUN FILE_NAME=linux_geo${RELEASE}_${MAJOR}.${MINOR}.zip \
  && curl -sSO https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/geosupport/$FILE_NAME \
  && unzip -q *.zip \
  && rm *.zip

ENV GEOFILES=/geosupport/version-${RELEASE}_${MAJOR}.${MINOR}/fls/
ENV LD_LIBRARY_PATH=/geosupport/version-${RELEASE}_${MAJOR}.${MINOR}/lib/

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8080
CMD ["python", "app.py"]
