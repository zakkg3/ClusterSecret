from typing import List, Dict, Any

from pydantic import BaseModel


class BaseClusterSecret(BaseModel):
    uid: str
    name: str
    namespace: str
    body: Dict[str, Any]
    synced_namespace: List[str]
