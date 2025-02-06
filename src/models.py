from typing import List, Dict, Any

from pydantic import BaseModel


class BaseClusterSecret(BaseModel):
    uid: str
    name: str
    body: Dict[str, Any]
