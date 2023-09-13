import unittest

from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Load Kubernetes configuration from the default location or provide your own kubeconfig file path
from k8s_utils import wait_for_pod_ready_with_events, ClusterSecretManager

config.load_kube_config()

# Create a Kubernetes API client
api_instance = client.CoreV1Api()
custom_objects_api = client.CustomObjectsApi()

CLUSTER_SECRET_NAMESPACE = "cluster-secret"
USER_NAMESPACES = ["example-1", "example-2", "example-3"]


class ClusterSecretCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Wait for the cluster secret pod to be ready before running tests
        wait_for_pod_ready_with_events({'app': 'clustersecret'}, namespace=CLUSTER_SECRET_NAMESPACE, timeout_seconds=60)

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
        cluster_secret_manager = ClusterSecretManager(
            custom_objects_api=custom_objects_api,
            api_instance=api_instance
        )

        cluster_secret_manager.create_cluster_secret(
            name=name,
            namespace=USER_NAMESPACES[0],
            data={"username": username_data}
        )

        # We expect the secret to be in ALL namespaces
        self.assertTrue(
            cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
            )
        )

    def test_complex_cluster_secret(self):
        name = "complex-cluster-secret"
        username_data = "MTIzNDU2Cg=="
        cluster_secret_manager = ClusterSecretManager(
            custom_objects_api=custom_objects_api,
            api_instance=api_instance
        )

        # Create a secret in all user namespace expect the first one
        cluster_secret_manager.create_cluster_secret(
            name=name,
            namespace=USER_NAMESPACES[0],
            data={"username": username_data},
            match_namespace=["example-*"],
            avoid_namespaces=[USER_NAMESPACES[0]]
        )

        # Ensure the secrets is only present where is to suppose to be
        self.assertTrue(
            cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
                namespaces=USER_NAMESPACES[1:],
            ),
        )

    def test_patch_cluster_secret_data(self):
        name = "dynamic-cluster-secret"
        username_data = "MTIzNDU2Cg=="
        updated_data = "Nzg5MTAxMTIxMgo="
        cluster_secret_manager = ClusterSecretManager(
            custom_objects_api=custom_objects_api,
            api_instance=api_instance
        )

        # Create a secret with username_data
        cluster_secret_manager.create_cluster_secret(
            name=name,
            namespace=USER_NAMESPACES[0],
            data={"username": username_data},
        )

        # Ensure the secret is created with the right data
        self.assertTrue(
            cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
            )
        )

        # Update the cluster secret's data
        cluster_secret_manager.update_data_cluster_secret(
            name=name,
            data={"username": updated_data},
            namespace=USER_NAMESPACES[0],
        )

        # Ensure the secrets are updated with the right data (at some point)
        self.assertTrue(
            cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": updated_data},
            ),
            f'secret {name} should be in all user namespaces',
        )

    def test_patch_cluster_secret_match_namespaces(self):
        name = "dynamic-cluster-secret-match-namespaces"
        username_data = "MTIzNDU2Cg=="
        cluster_secret_manager = ClusterSecretManager(
            custom_objects_api=custom_objects_api,
            api_instance=api_instance
        )

        cluster_secret_manager.create_cluster_secret(
            name=name,
            namespace=USER_NAMESPACES[0],
            data={"username": username_data},
            match_namespace=[
                USER_NAMESPACES[0]
            ]
        )

        self.assertTrue(
            cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
                namespaces=[
                    USER_NAMESPACES[0]
                ],
            ),
            f'secret should be only in namespace {USER_NAMESPACES[0]}'
        )

        # Update the cluster match_namespace to ALL user namespace
        cluster_secret_manager.update_data_cluster_secret(
            name=name,
            namespace=USER_NAMESPACES[0],
            match_namespace=USER_NAMESPACES,
            data={"username": username_data},
        )

        self.assertTrue(
            cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
                namespaces=USER_NAMESPACES,
            ),
            f'secret {name} should be in all user namespaces'
        )

    def test_simple_cluster_secret_deleted(self):
        name = "simple-cluster-secret-deleted"
        username_data = "MTIzNDU2Cg=="
        cluster_secret_manager = ClusterSecretManager(
            custom_objects_api=custom_objects_api,
            api_instance=api_instance
        )

        cluster_secret_manager.create_cluster_secret(
            name=name,
            namespace=USER_NAMESPACES[0],
            data={"username": username_data}
        )

        # We expect the secret to be in ALL namespaces
        self.assertTrue(
            cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data}
            )
        )

        cluster_secret_manager.delete_cluster_secret(
            name=name,
            namespace=USER_NAMESPACES[0],
        )

        # We expect the secret to be in NO namespaces
        self.assertTrue(
            cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
                namespaces=[],
            ),
            f'secret {name} should be deleted from all namespaces.'
        )


if __name__ == '__main__':
    unittest.main()
