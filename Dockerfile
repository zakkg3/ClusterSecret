FROM flag5/clustersecretbase:0.0.5
ADD /src /src

RUN adduser --system --no-create-home secretmonkey
USER secretmonkey
CMD kopf run --liveness=http://0.0.0.0:8080/healthz -A /src/handlers.py
