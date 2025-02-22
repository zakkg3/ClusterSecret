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
            reason="update",
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
                reason="update",
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
                    reason="create",
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

    def test_ns_delete(self):
        """Deleted namespace must be removed from cluster secret 'status.create_fn.syncedns' filed.
        """

        mock_v1 = Mock()

        # Define the predefined list of namespaces you want to use in the test (after namespace deletion)
        predefined_nss = [Mock(metadata=V1ObjectMeta(name=ns)) for ns in ["default"]]

        # Configure the mock's behavior to return the predefined namespaces when list_namespace is called
        mock_v1.list_namespace.return_value.items = predefined_nss

        patch_clustersecret_status = Mock()

        # The list of synced namespaces here are before namespace deletion handler is called
        csec = BaseClusterSecret(
            uid="mysecretuid",
            name="mysecret",
            body={"metadata": {"name": "mysecret"}, "data": "mydata"},
            synced_namespace=["default", "myns"],
        )

        csecs_cache.set_cluster_secret(csec)

        with patch("handlers.v1", mock_v1), \
             patch("handlers.patch_clustersecret_status", patch_clustersecret_status):
            asyncio.run(
                namespace_watcher(
                    logger=self.logger,
                    meta=kopf.Meta({"metadata": {"name": "myns"}}),
                    reason="delete",
                )
            )

        # The syncedns status of the clustersecret should not contains deleted namespace.
        patch_clustersecret_status.assert_called_once_with(
            logger=self.logger,
            name=csec.name,
            new_status={'create_fn': {'syncedns': ["default"]}},
            custom_objects_api=custom_objects_api,
        )

        # The deleted namespace should not be in the cache.
        self.assertCountEqual(
            csecs_cache.get_cluster_secret("mysecretuid").synced_namespace,
            ["default"],
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
