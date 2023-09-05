import unittest
from typing import Callable, Dict, Optional
from time import sleep
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Load Kubernetes configuration from the default location or provide your own kubeconfig file path
config.load_kube_config()

# Create a Kubernetes API client
api_instance = client.CoreV1Api()
custom_objects_api = client.CustomObjectsApi()

CLUSTER_SECRET_NAMESPACE = "cluster-secret"
USER_NAMESPACES = ["example-1", "example-2", "example-3"]


def retry(f: Callable[[], bool], retries=3, delay=5):
    while retries > 0:
        if f():
            return True
        sleep(delay)
        retries -= 1
    return False


def create_cluster_secret(
        name: str,
        namespace: str,
        data: Dict[str, str],
        labels: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, str]] = None,
):
    return custom_objects_api.create_namespaced_custom_object(
        group="clustersecret.io",
        version="v1",
        namespace=namespace,
        body={
            "apiVersion": "clustersecret.io/v1",
            "kind": "ClusterSecret",
            "metadata": {"name": name, "labels": labels, "annotations": annotations},
            "data": data
        },
        plural="clustersecrets",
    )


class ClusterSecretCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        # Create namespaces for tests
        for namespace_name in USER_NAMESPACES:
            namespace = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace_name))
            try:
                api_instance.create_namespace(namespace)
                print(f"Namespace '{namespace_name}' created successfully.")
            except client.rest.ApiException as e:
                if e.status == 409:
                    print(f"Namespace '{namespace_name}' already exists.")
                else:
                    print(f"Error creating namespace '{namespace_name}': {e}")
        super().setUpClass()

    def test_running(self):
        pods = api_instance.list_namespaced_pod(namespace=CLUSTER_SECRET_NAMESPACE)
        self.assertEqual(len(pods.items), 1)

    def test_simple_cluster_secret(self):
        name = "simple-cluster-secret"
        username_data = "MTIzNDU2Cg=="

        create_cluster_secret(name=name, namespace=USER_NAMESPACES[0], data={"username": username_data})

        def get_secret():
            secrets = api_instance.list_namespaced_secret(
                namespace=USER_NAMESPACES[1]
            )

            if len(secrets.items) != 1:
                return False

            self.assertEqual(secrets.items[1].metadata.name, name)
            self.assertEqual(secrets.items[0].data['username'], username_data)

            return True

        self.assertTrue(retry(get_secret))


if __name__ == '__main__':
    unittest.main()
