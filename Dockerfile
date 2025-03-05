ARG ARCH=""
FROM ${ARCH}python:3.9-slim
ADD /src /src
RUN apt update && apt install -y build-essential
RUN pip install -r /src/requirements.txt
RUN adduser --system --no-create-home secretmonkey
USER secretmonkey
CMD kopf run --liveness=http://[::]:8080/healthz -A /src/handlers.py
