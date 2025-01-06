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

    def setUp(self) -> None:
        self.cluster_secret_manager = ClusterSecretManager(
            custom_objects_api=custom_objects_api,
            api_instance=api_instance
        )
        super().setUp()

    def tearDown(self) -> None:
        self.cluster_secret_manager.cleanup()
        super().tearDown()

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

        self.cluster_secret_manager.create_cluster_secret(
            name=name,
            data={"username": username_data}
        )

        # We expect the secret to be in ALL namespaces
        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
            )
        )

    def test_complex_cluster_secret(self):
        name = "complex-cluster-secret"
        username_data = "MTIzNDU2Cg=="

        # Create a secret in all user namespace expect the first one
        self.cluster_secret_manager.create_cluster_secret(
            name=name,
            data={"username": username_data},
            match_namespace=["example-*"],
            avoid_namespaces=[USER_NAMESPACES[0]]
        )

        # Ensure the secrets is only present where is to suppose to be
        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
                namespaces=USER_NAMESPACES[1:],
            ),
        )

    def test_patch_cluster_secret_data(self):
        name = "dynamic-cluster-secret"
        username_data = "MTIzNDU2Cg=="
        updated_data = "Nzg5MTAxMTIxMgo="

        # Create a secret with username_data
        self.cluster_secret_manager.create_cluster_secret(
            name=name,
            data={"username": username_data},
        )

        # Ensure the secret is created with the right data
        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
            )
        )

        # Update the cluster secret's data
        self.cluster_secret_manager.update_data_cluster_secret(
            name=name,
            data={"username": updated_data},
        )

        # Ensure the secrets are updated with the right data (at some point)
        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": updated_data},
            ),
            f'secret {name} should be in all user namespaces',
        )

    def test_patch_cluster_secret_match_namespaces(self):
        name = "dynamic-cluster-secret-match-namespaces"
        username_data = "MTIzNDU2Cg=="

        self.cluster_secret_manager.create_cluster_secret(
            name=name,
            data={"username": username_data},
            match_namespace=[
                USER_NAMESPACES[0]
            ]
        )

        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
                namespaces=[
                    USER_NAMESPACES[0]
                ],
            ),
            f'secret should be only in namespace {USER_NAMESPACES[0]}'
        )

        # Update the cluster match_namespace to ALL user namespace
        self.cluster_secret_manager.update_data_cluster_secret(
            name=name,
            match_namespace=USER_NAMESPACES,
            data={"username": username_data},
        )

        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
                namespaces=USER_NAMESPACES,
            ),
            f'secret {name} should be in all user namespaces'
        )

    def test_simple_cluster_secret_deleted(self):
        name = "simple-cluster-secret-deleted"
        username_data = "MTIzNDU2Cg=="

        self.cluster_secret_manager.create_cluster_secret(
            name=name,
            data={"username": username_data}
        )

        # We expect the secret to be in ALL namespaces
        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data}
            )
        )

        self.cluster_secret_manager.delete_cluster_secret(
            name=name,
        )

        # We expect the secret to be in NO namespaces
        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
                namespaces=[],
            ),
            f'secret {name} should be deleted from all namespaces.'
        )

    def test_value_from_cluster_secret(self):
        cluster_secret_name = "value-from-cluster-secret"
        secret_name = "basic-secret-example"

        username_data = "MTIzNDU2Cg=="

        # Create a kubernetes secrets
        self.cluster_secret_manager.create_secret(
            name=secret_name,
            namespace=USER_NAMESPACES[0],
            data={'username': username_data}
        )

        # Create the cluster secret
        self.cluster_secret_manager.create_cluster_secret(
            name=cluster_secret_name,
            secret_key_ref={
                'name': secret_name,
            },
        )

        # We expect the secret to be in ALL namespaces
        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=cluster_secret_name,
                data={"username": username_data},
            ),
            msg=f'Cluster secret should take the data from the {secret_name} secret.'
        )

    def test_value_from_with_keys_cluster_secret(self):
        cluster_secret_name = "value-from-with-keys-cluster-secret"
        secret_name = "k8s-basic-secret-example"

        username_data = "MTIzNDU2Cg=="
        password_data = "aGloaXBhc3M="
        more_data = "aWlpaWlhYWE="

        # Create a kubernetes secrets
        self.cluster_secret_manager.create_secret(
            name=secret_name,
            namespace=USER_NAMESPACES[0],
            data={'username': username_data, 'password': password_data, 'more-data': more_data}
        )

        # Create the cluster secret
        self.cluster_secret_manager.create_cluster_secret(
            name=cluster_secret_name,
            secret_key_ref={
                'name': secret_name,
                'keys': ['username', 'password']
            },
        )

        # We expect the secret to be in ALL namespaces
        self.assertTrue(
            self.cluster_secret_manager.validate_namespace_secrets(
                name=cluster_secret_name,
                data={'username': username_data, 'password': password_data},
            ),
            msg=f'Cluster secret should take the data from the {secret_name} secret but only the keys specified.'
        )

    def test_simple_cluster_secret_with_annotation(self):
        name = "simple-cluster-secret-annotation"
        username_data = "MTIzNDU2Cg=="
        annotations = {
            'custom-annotation': 'example',
        }
        cluster_secret_manager = ClusterSecretManager(
            custom_objects_api=custom_objects_api,
            api_instance=api_instance
        )

        cluster_secret_manager.create_cluster_secret(
            name=name,
            data={"username": username_data},
            annotations=annotations,
        )

        # We expect the secret to be in ALL namespaces
        self.assertTrue(
            cluster_secret_manager.validate_namespace_secrets(
                name=name,
                data={"username": username_data},
                annotations=annotations
            )
        )


if __name__ == '__main__':
    unittest.main()
