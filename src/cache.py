from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from models import BaseClusterSecret


class Cache(ABC):
    @abstractmethod
    def get_cluster_secret(self, uid: str) -> Optional[BaseClusterSecret]:
        pass

    @abstractmethod
    def set_cluster_secret(self, cluster_secret: BaseClusterSecret):
        pass

    @abstractmethod
    def remove_cluster_secret(self, uid: str):
        pass

    @abstractmethod
    def all_cluster_secret(self) -> List[BaseClusterSecret]:
        pass

    def has_cluster_secret(self, uid: str) -> bool:
        return self.get_cluster_secret(uid) is not None


class MemoryCache(Cache):
    def __init__(self) -> None:
        self.csecs: Dict[str, BaseClusterSecret] = {}

    def get_cluster_secret(self, uid: str) -> Optional[BaseClusterSecret]:
        return self.csecs.get(uid, None)

    def set_cluster_secret(self, cluster_secret: BaseClusterSecret):
        self.csecs[cluster_secret.uid] = cluster_secret

    def remove_cluster_secret(self, uid: str):
        self.csecs.pop(uid)

    def all_cluster_secret(self) -> List[BaseClusterSecret]:
        return list(self.csecs.values())
