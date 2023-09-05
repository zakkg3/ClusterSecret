import unittest
from typing import Callable, Dict, Optional, List, Any
from time import sleep
from kubernetes import client, config
from kubernetes.client import V1Secret
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
        match_namespace: Optional[List[str]] = None,
        avoid_namespaces: Optional[List[str]] = None,
):
    return custom_objects_api.create_namespaced_custom_object(
        group="clustersecret.io",
        version="v1",
        namespace=namespace,
        body={
            "apiVersion": "clustersecret.io/v1",
            "kind": "ClusterSecret",
            "metadata": {"name": name, "labels": labels, "annotations": annotations},
            "data": data,
            "matchNamespace": match_namespace,
            "avoidNamespaces": avoid_namespaces,
        },
        plural="clustersecrets",
    )


def update_data_cluster_secret(
        name: str,
        namespace: str,
        data: Dict[str, str],
):
    custom_objects_api.patch_namespaced_custom_object(
        name=name,
        group="clustersecret.io",
        version="v1",
        namespace=namespace,
        body={
            "apiVersion": "clustersecret.io/v1",
            "kind": "ClusterSecret",
            "data": data,
        },
        plural="clustersecrets",
    )


def get_kubernetes_secret(name: str, namespace: str) -> Optional[V1Secret]:
    try:
        return api_instance.read_namespaced_secret(name, namespace)
    except ApiException as e:
        if e.status == 404:
            return None
        else:
            raise e


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

        def validate():
            for namespace in USER_NAMESPACES:
                secret = get_kubernetes_secret(
                    name=name,
                    namespace=namespace
                )

                if secret is None:
                    return False

                self.assertEqual(secret.data['username'], username_data)

            return True

        self.assertTrue(retry(validate))

    def test_complex_cluster_secret(self):
        name = "complex-cluster-secret"
        username_data = "MTIzNDU2Cg=="

        create_cluster_secret(
            name=name,
            namespace=USER_NAMESPACES[0],
            data={"username": username_data},
            match_namespace=["example-*"],
            avoid_namespaces=[USER_NAMESPACES[0]]
        )

        # Ensure the secret is in all USER_NAMESPACES except the last one
        def validate():
            for namespace in USER_NAMESPACES[1:]:
                secret = get_kubernetes_secret(
                    name=name,
                    namespace=namespace
                )

                if secret is None:
                    return False

                self.assertEqual(secret.data['username'], username_data)

            secrets = api_instance.list_namespaced_secret(
                namespace=USER_NAMESPACES[0]
            )

            self.assertEqual(len([secret for secret in secrets.items if secret.metadata.name == name]), 0)
            return True

        self.assertTrue(retry(validate))

    def test_patch_cluster_secret(self):
        name = "dynamic-cluster-secret"
        username_data = "MTIzNDU2Cg=="
        updated_data = "Nzg5MTAxMTIxMgo="

        create_cluster_secret(name=name, namespace=USER_NAMESPACES[0], data={"username": username_data})

        def validate():
            for namespace in USER_NAMESPACES:
                secret = get_kubernetes_secret(
                    name=name,
                    namespace=namespace
                )

                if secret is None:
                    return False

                self.assertEqual(secret.data['username'], username_data)

            return True

        self.assertTrue(retry(validate))

        update_data_cluster_secret(name=name, data={"username": updated_data}, namespace=USER_NAMESPACES[0])

        def validate():
            for namespace in USER_NAMESPACES:
                secret = get_kubernetes_secret(
                    name=name,
                    namespace=namespace
                )

                if secret.data['username'] != updated_data:
                    return False

            return True

        self.assertTrue(retry(validate))

    @classmethod
    def tearDownClass(cls) -> None:
        # TODO: cleanup namespaces + ClusterSecrets
        super().tearDownClass()


if __name__ == '__main__':
    unittest.main()
