FROM flag5/clustersecretbase:0.0.2
ADD /src /src
CMD kopf run /src/handlers.py
