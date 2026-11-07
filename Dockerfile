# Public source mirror of Muster's league commissioner (for coworld certification
# source-resolves). The LIVE image is built from ~/muster-coworld/coworld_pkg/
# commissioner.Dockerfile; this Dockerfile mirrors it so the manifest's commissioner
# source_url resolves to a PUBLIC, buildable context. See README.
FROM ghcr.io/softmax-universe/commissioners-default@sha256:077099a326df51d684168426b606f55146201fec3553c53ae060aca26a533bad

COPY muster-commissioner.yaml /config/muster-commissioner.yaml
ENV RULESET_STRATEGY_CONFIG_PATH=/config/muster-commissioner.yaml

RUN mkdir -p /app/coworld_pkg && printf '' > /app/coworld_pkg/__init__.py
COPY coworld_pkg/commissioner /app/coworld_pkg/commissioner

ENV COMMISSIONER_KEY=muster
CMD ["uvicorn", "coworld_pkg.commissioner.app:app", "--host", "0.0.0.0", "--port", "8080"]
