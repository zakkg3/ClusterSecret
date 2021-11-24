FROM flag5/clustersecretbase:0.0.5
ADD /src /src
CMD kopf run -A /src/handlers.py
