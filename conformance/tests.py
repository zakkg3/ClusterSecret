import unittest
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Load Kubernetes configuration from the default location or provide your own kubeconfig file path
config.load_kube_config()

# Create a Kubernetes API client
api_instance = client.CoreV1Api()
custom_objects_api = client.CustomObjectsApi()

CLUSTER_SECRET_NAMESPACE = "cluster-secret"
USER_NAMESPACES = ["example-1", "example-2", "example-3"]


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
        custom_objects_api.create_namespaced_custom_object(
            group="clustersecret.io",
            version="v1",
            namespace=USER_NAMESPACES[0],
            body={
                "apiVersion": "clustersecret.io/v1",
                "kind": "ClusterSecret",
                "metadata": {"name": "simple-cluster-secret"},
                "data": {"username": "MTIzNDU2Cg=="}
            },
            plural="clustersecrets",
        )

        secrets = api_instance.list_namespaced_secret(
            namespace=USER_NAMESPACES[1]
        )
        self.assertEqual(len(secrets.items), 1)


if __name__ == '__main__':
    unittest.main()
