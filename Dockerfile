FROM flag5/clustersecretbase:0.0.4
ADD /src /src
CMD kopf run /src/handlers.py
