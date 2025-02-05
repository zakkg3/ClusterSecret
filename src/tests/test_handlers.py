import asyncio
import kopf
import logging
import unittest

from kubernetes.client import V1ObjectMeta, V1Secret, ApiException
from unittest.mock import ANY, Mock, patch

from handlers import create_fn, custom_objects_api, csecs_cache, namespace_watcher, on_field_data, startup_fn
from kubernetes_utils import create_secret_metadata
from models import BaseClusterSecret


class TestClusterSecretHandler(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger(__name__)
        for cluster_secret in csecs_cache.all_cluster_secret():
            csecs_cache.remove_cluster_secret(cluster_secret.uid)

    def test_on_field_data_cache(self):
        """New data should be written into the cache.
        """

        # Old data in the cache.
        csec = BaseClusterSecret(
            uid="mysecretuid",
            name="mysecret",
            body={"metadata": {"name": "mysecret", "uid": "mysecretuid"}, "data": {"key": "oldvalue"}},
            synced_namespace=[],
        )

        csecs_cache.set_cluster_secret(csec)

        # New data coming into the callback.
        new_body = {"metadata": {"name": "mysecret", "uid": "mysecretuid"}, "data": {"key": "newvalue"}}

        on_field_data(
            old={"key": "oldvalue"},
            new={"key": "newvalue"},
            body=new_body,
            meta=kopf.Meta({"metadata": {"name": "mysecret"}}),
            name="mysecret",
            uid="mysecretuid",
            logger=self.logger,
        )

        # New data should be in the cache.
        self.assertEqual(
            csecs_cache.get_cluster_secret("mysecretuid").body.get("data"),
            {"key": "newvalue"},
        )

    def test_on_field_data_sync(self):
        """Must sync secret data changes to the namespaces.
        """

        mock_v1 = Mock()

        # Old data in the namespaced secret of the myns namespace.
        mock_v1.read_namespaced_secret.return_value = V1Secret(
            api_version='v1',
            data={"key": "oldvalue"},
            kind='Secret',
            metadata=create_secret_metadata(
                name="mysecret",
                namespace="myns",
            ),
            type="Opaque",
        )

        # Old data in the cache.
        csec = BaseClusterSecret(
            uid="mysecretuid",
            name="mysecret",
            body={
                "metadata": {"name": "mysecret", "uid": "mysecretuid"},
                "data": {"key": "oldvalue"},
                "status": {"create_fn": {"syncedns": ["myns"]}},
            },
            synced_namespace=["myns"],
        )

        csecs_cache.set_cluster_secret(csec)

        # New data coming into the callback.
        new_body = {
            "metadata": {"name": "mysecret", "uid": "mysecretuid"},
            "data": {"key": "newvalue"},
            "status": {"create_fn": {"syncedns": ["myns"]}},
        }

        with patch("handlers.v1", mock_v1):
            on_field_data(
                old={"key": "oldvalue"},
                new={"key": "newvalue"},
                body=new_body,
                meta=kopf.Meta({"metadata": {"name": "mysecret"}}),
                name="mysecret",
                uid="mysecretuid",
                logger=self.logger,
            )

        # Namespaced secret should be updated.
        mock_v1.replace_namespaced_secret.assert_called_once_with(
            name=csec.name,
            namespace="myns",
            body=ANY,
        )

        # Namespaced secret should be updated with the new data.
        self.assertEqual(
            mock_v1.replace_namespaced_secret.call_args.kwargs.get("body").data,
            {"key": "newvalue"},
        )

    def test_on_field_data_ns_deleted(self):
        """Don't fail the sync if one of the namespaces was deleted.
        """

        mock_v1 = Mock()

        def read_namespaced_secret(name, namespace, **kwargs):
            if namespace == "myns2":
                # Old data in the namespaced secret of the myns namespace.
                return V1Secret(
                    api_version='v1',
                    data={"key": "oldvalue"},
                    kind='Secret',
                    metadata=create_secret_metadata(
                        name="mysecret",
                        namespace="myns2",
                    ),
                    type="Opaque",
                )
            else:
                # Deleted namespace.
                raise ApiException(status=404, reason="Not Found")

        mock_v1.read_namespaced_secret = read_namespaced_secret

        create_namespaced_secret_called_count_for_ns2 = 0

        def create_namespaced_secret(namespace, body, **kwargs):
            if namespace == "myns2":
                nonlocal create_namespaced_secret_called_count_for_ns2
                create_namespaced_secret_called_count_for_ns2 += 1
            else:
                # Deleted namespace.
                raise ApiException(status=404, reason="Not Found")

        mock_v1.create_namespaced_secret = create_namespaced_secret

        replace_namespaced_secret_called_count_for_ns2 = 0

        def replace_namespaced_secret(name, namespace, body, **kwargs):
            if namespace == "myns2":
                nonlocal replace_namespaced_secret_called_count_for_ns2
                replace_namespaced_secret_called_count_for_ns2 += 1
                self.assertEqual(name, csec.name)

                # Namespaced secret should be updated with the new data.
                self.assertEqual(
                    body.data,
                    {"key": "newvalue"},
                )

                return V1Secret(
                    api_version='v1',
                    data=body.data,
                    kind='Secret',
                    metadata=create_secret_metadata(
                        name="mysecret",
                        namespace="myns2",
                    ),
                    type="Opaque",
                )
            else:
                # Deleted namespace.
                raise ApiException(status=404, reason="Not Found")

        mock_v1.replace_namespaced_secret = replace_namespaced_secret

        def read_namespace(name, **kwargs):
            if name != "myns2":
                # Deleted namespace.
                raise ApiException(status=404, reason="Not Found")

        mock_v1.read_namespace = read_namespace

        patch_clustersecret_status = Mock()
        patch_clustersecret_status.return_value = {
            "metadata": {"name": "mysecret", "uid": "mysecretuid"},
            "data": {"key": "newvalue"},
            "status": {"create_fn": {"syncedns": ["myns2"]}},
        }

        # Old data in the cache.
        csec = BaseClusterSecret(
            uid="mysecretuid",
            name="mysecret",
            body={
                "metadata": {"name": "mysecret", "uid": "mysecretuid"},
                "data": {"key": "oldvalue"},
                "status": {"create_fn": {"syncedns": ["myns1", "myns2"]}},
            },
            synced_namespace=["myns1", "myns2"],
        )

        csecs_cache.set_cluster_secret(csec)

        # New data coming into the callback.
        new_body = {
            "metadata": {"name": "mysecret", "uid": "mysecretuid"},
            "data": {"key": "newvalue"},
            "status": {"create_fn": {"syncedns": ["myns1", "myns2"]}},
        }

        with patch("handlers.v1", mock_v1), \
             patch("handlers.patch_clustersecret_status", patch_clustersecret_status):
            on_field_data(
                old={"key": "oldvalue"},
                new={"key": "newvalue"},
                body=new_body,
                meta=kopf.Meta({"metadata": {"name": "mysecret"}}),
                name="mysecret",
                uid="mysecretuid",
                logger=self.logger,
            )

        # Namespaced secret should be updated with the new data.
        self.assertEqual(replace_namespaced_secret_called_count_for_ns2, 1)
        self.assertEqual(create_namespaced_secret_called_count_for_ns2, 0)

        # The namespace should be deleted from the syncedns status of the clustersecret.
        patch_clustersecret_status.assert_called_once_with(
            logger=self.logger,
            name=csec.name,
            new_status={'create_fn': {'syncedns': ["myns2"]}},
            custom_objects_api=custom_objects_api,
        )

        # Namespace should be deleted from the cache.
        self.assertEqual(
            csecs_cache.get_cluster_secret("mysecretuid").body.get("status"),
            {"create_fn": {"syncedns": ["myns2"]}},
        )
        self.assertEqual(
            csecs_cache.get_cluster_secret("mysecretuid").synced_namespace,
            ["myns2"],
        )

    def test_create_fn(self):
        """Namespace name must be correct in the cache.
        """

        mock_v1 = Mock()

        body = {
            "metadata": {
                "name": "mysecret",
                "uid": "mysecretuid"
            },
            "data": {"key": "value"}
        }

        # Define the predefined list of namespaces you want to use in the test
        predefined_nss = [Mock(metadata=V1ObjectMeta(name=ns)) for ns in ["default", "myns"]]

        # Configure the mock's behavior to return the predefined namespaces when list_namespace is called
        mock_v1.list_namespace.return_value.items = predefined_nss

        with patch("handlers.v1", mock_v1), \
             patch("handlers.sync_secret"):
            asyncio.run(
                create_fn(
                    logger=self.logger,
                    uid="mysecretuid",
                    name="mysecret",
                    body=body,
                )
            )

        # The secrets should be in all namespaces of the cache.
        self.assertEqual(
            csecs_cache.get_cluster_secret("mysecretuid").synced_namespace,
            ["default", "myns"],
        )

    def test_ns_create(self):
        """A new namespace must get the cluster secrets.
        """

        mock_v1 = Mock()

        # Define the predefined list of namespaces you want to use in the test
        predefined_nss = [Mock(metadata=V1ObjectMeta(name=ns)) for ns in ["default", "myns"]]

        # Configure the mock's behavior to return the predefined namespaces when list_namespace is called
        mock_v1.list_namespace.return_value.items = predefined_nss

        patch_clustersecret_status = Mock()

        csec = BaseClusterSecret(
            uid="mysecretuid",
            name="mysecret",
            body={"metadata": {"name": "mysecret"}, "data": "mydata"},
            synced_namespace=["default"],
        )

        csecs_cache.set_cluster_secret(csec)

        with patch("handlers.v1", mock_v1), \
             patch("handlers.patch_clustersecret_status", patch_clustersecret_status):
            asyncio.run(
                namespace_watcher(
                    logger=self.logger,
                    meta=kopf.Meta({"metadata": {"name": "myns"}}),
                )
            )

        # The new namespace should have the secret copied into it.
        mock_v1.replace_namespaced_secret.assert_called_once_with(
            name=csec.name,
            namespace="myns",
            body=ANY,
        )

        # The namespace should be added to the syncedns status of the clustersecret.
        patch_clustersecret_status.assert_called_once_with(
            logger=self.logger,
            name=csec.name,
            new_status={'create_fn': {'syncedns': ["default", "myns"]}},
            custom_objects_api=custom_objects_api,
        )

        # The new namespace should be in the cache.
        self.assertCountEqual(
            csecs_cache.get_cluster_secret("mysecretuid").synced_namespace,
            ["default", "myns"],
        )

    def test_startup_fn(self):
        """Must not fail on empty namespace in ClusterSecret metadata (it's cluster-wide after all).
        """

        get_custom_objects_by_kind = Mock()

        csec = BaseClusterSecret(
            uid="mysecretuid",
            name="mysecret",
            body={"metadata": {"name": "mysecret", "uid": "mysecretuid"}, "data": "mydata"},
            synced_namespace=[],
        )

        get_custom_objects_by_kind.return_value = [csec.body]

        with patch("handlers.get_custom_objects_by_kind", get_custom_objects_by_kind):
            asyncio.run(startup_fn(logger=self.logger))

        # The secret should be in the cache.
        self.assertEqual(
            csecs_cache.get_cluster_secret("mysecretuid"),
            csec,
        )
