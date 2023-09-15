import time
from typing import Dict, Optional, List, Callable, Mapping, Any
from kubernetes import client, config
from kubernetes.client import V1Secret, CoreV1Api, CustomObjectsApi
from kubernetes.client.rest import ApiException
from time import sleep


def is_subset(_set: Mapping[str, str], _subset: Mapping[str, str]) -> bool:
    for key, item in _subset.items():
        if _set.get(key, None) != item:
            return False
    return True


def wait_for_pod_ready_with_events(pod_selector: dict, namespace: str, timeout_seconds: int = 300):
    """
    Wait for a pod to be ready in the specified namespace and print all events.

    Args:
        pod_selector (dict): A dictionary representing the pod selector (e.g., {"app": "my-app"}).
        namespace (str): The namespace where the pod is located.
        timeout_seconds (int): Maximum time to wait for the pod to become ready (default: 300 seconds).

    Raises:
        TimeoutError: If the specified pod does not become ready within the timeout.
    """
    config.load_kube_config()
    v1 = client.CoreV1Api()

    end_time = time.time() + timeout_seconds

    while time.time() < end_time:
        pod_list = v1.list_namespaced_pod(
            namespace,
            label_selector=','.join([f"{k}={v}" for k, v in pod_selector.items()])
        )

        for pod in pod_list.items:
            pod_name = pod.metadata.name
            print(f"Checking pod {pod_name}...")

            # Print pod events
            events = v1.list_namespaced_event(namespace, field_selector=f"involvedObject.name={pod_name}")
            for event in events.items:
                print(f"Event: {event.message}")

            # Check if the pod is ready
            if all(status.ready for status in pod.status.container_statuses):
                print(f"Pod {pod_name} is ready!")
                return

        time.sleep(5)  # Sleep for a few seconds before checking again

    raise TimeoutError(f"Timed out waiting for pod to become ready in namespace {namespace}")


class ClusterSecretManager:
    def __init__(self, custom_objects_api: CustomObjectsApi, api_instance: CoreV1Api):
        self.custom_objects_api: CustomObjectsApi = custom_objects_api
        self.api_instance: CoreV1Api = api_instance
        # immutable after
        self.retry_attempts = 3
        self.retry_delay = 5

    def create_secret(
            self,
            name: str,
            namespace: str,
            data: Dict[str, Any],
            labels: Optional[Dict[str, str]] = None,
            annotations: Optional[Dict[str, str]] = None,
    ):
        self.api_instance.create_namespaced_secret(
            namespace=namespace,
            body=client.V1Secret(
                metadata=client.V1ObjectMeta(
                    name=name,
                    labels=labels,
                    annotations=annotations,
                ),
                data=data,
            ),
        )

    @staticmethod
    def _generate_secret_key_ref_dict(secret_key_ref: Dict[str, str]) -> Dict[str, Any]:
        if secret_key_ref.get('name', None) is None or secret_key_ref.get('namespace', None) is None:
            raise Exception(f'secretKeyRef dict should have a name and a namespace property defined.')

        return (
            {
                "valueFrom": {
                    "secretKeyRef": {
                        "name": secret_key_ref.get('name'),
                        "namespace": secret_key_ref.get('namespace'),
                        "keys": secret_key_ref.get('keys'),
                    },
                },
            }
        )

    def create_cluster_secret(
            self,
            name: str,
            namespace: str,
            data: Optional[Dict[str, Any]] = None,
            secret_key_ref: Optional[Dict[str, str]] = None,
            labels: Optional[Dict[str, str]] = None,
            annotations: Optional[Dict[str, str]] = None,
            match_namespace: Optional[List[str]] = None,
            avoid_namespaces: Optional[List[str]] = None,
    ):
        if data is None and secret_key_ref is None:
            raise Exception('You need to either define data or secret_key_ref.')

        return self.custom_objects_api.create_namespaced_custom_object(
            group="clustersecret.io",
            version="v1",
            namespace=namespace,
            body={
                "apiVersion": "clustersecret.io/v1",
                "kind": "ClusterSecret",
                "metadata": {"name": name, "labels": labels, "annotations": annotations},
                "data": data if data is not None else self._generate_secret_key_ref_dict(secret_key_ref),
                "matchNamespace": match_namespace,
                "avoidNamespaces": avoid_namespaces,
            },
            plural="clustersecrets",
        )

    def update_data_cluster_secret(
            self,
            name: str,
            namespace: str,
            data: Dict[str, str],
            match_namespace: Optional[List[str]] = None,
            avoid_namespaces: Optional[List[str]] = None,
    ):
        self.custom_objects_api.patch_namespaced_custom_object(
            name=name,
            group="clustersecret.io",
            version="v1",
            namespace=namespace,
            body={
                "apiVersion": "clustersecret.io/v1",
                "kind": "ClusterSecret",
                "data": data,
                "matchNamespace": match_namespace,
                "avoidNamespaces": avoid_namespaces,
            },
            plural="clustersecrets",
        )

    def delete_cluster_secret(
            self,
            name: str,
            namespace: str
    ):
        self.custom_objects_api.delete_namespaced_custom_object(
            name=name,
            group="clustersecret.io",
            version="v1",
            namespace=namespace,
            plural="clustersecrets",
        )

    def get_kubernetes_secret(self, name: str, namespace: str) -> Optional[V1Secret]:
        try:
            return self.api_instance.read_namespaced_secret(name, namespace)
        except ApiException as e:
            if e.status == 404:
                return None
            else:
                raise e

    def validate_namespace_secrets(
            self,
            name: str,
            data: Dict[str, str],
            namespaces: Optional[List[str]] = None,
            labels: Optional[Dict[str, str]] = None,
            annotations: Optional[Dict[str, str]] = None,
    ) -> bool:
        """

        Parameters
        ----------
        name: str
        data: Dict[str, str]
        namespaces: Optional[List[str]]
            If None, it means the secret should be present in ALL namespaces
        annotations: Optional[Dict[str, str]]
        labels: Optional[Dict[str, str]]

        Returns
        -------

        """
        all_namespaces = [item.metadata.name for item in self.api_instance.list_namespace().items]

        def validate():
            for namespace in all_namespaces:

                secret = self.get_kubernetes_secret(name=name, namespace=namespace)

                if namespaces is not None and namespace not in namespaces:
                    if secret is None:
                        continue
                    return False

                if secret is None or secret.data != data:
                    return False

                if annotations is not None and not is_subset(secret.metadata.annotations, annotations):
                    return False

                if labels is not None and not is_subset(secret.metadata.labels, labels):
                    return False

            return True

        return self.retry(validate)

    def retry(self, f: Callable[[], bool]) -> bool:
        """
        Utility function
        Parameters
        ----------
        f

        Returns
        -------

        """
        retry = self.retry_attempts
        while retry > 0:
            if f():
                return True
            sleep(self.retry_delay)
            retry -= 1
        return False

    def cleanup(self):
        # TODO: cleanup all secrets and cluster secrets created.
        pass
