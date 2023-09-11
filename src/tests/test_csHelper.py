import logging
import unittest

from kubernetes.client import V1ObjectMeta

from csHelper import get_ns_list
from unittest.mock import Mock

USER_NAMESPACE_COUNT = 10
initial_namespaces = ["default", "kube-node-lease", "kube-public", "kube-system"]
user_namespaces = [f'example-{i}' for i in range(USER_NAMESPACE_COUNT)]


class TestClusterSecret(unittest.TestCase):

    def test_get_ns_list(self):
        mock_v1 = Mock()

        # Define the predefined list of namespaces you want to use in the test
        predefined_nss = [Mock(metadata=V1ObjectMeta(name=ns)) for ns in initial_namespaces + user_namespaces]

        # Configure the mock's behavior to return the predefined namespaces when list_namespace is called
        mock_v1.list_namespace.return_value.items = predefined_nss

        cases = [
            {
                'name': 'No body defined',
                'body': {},
                'expected': initial_namespaces + user_namespaces,
            },
            {
                'name': 'Only user_namespaces',
                'body': {
                    'matchNamespace': ['example-*']
                },
                'expected': user_namespaces,
            },
            {
                'name': 'user_namespaces expect one',
                'body': {
                    'matchNamespace': ['example-*'],
                    'avoidNamespaces': ['example-0']
                },
                'expected': [f'example-{i}' for i in range(1, USER_NAMESPACE_COUNT)],
            },
            {
                'name': 'user_namespaces expect many',
                'body': {
                    'matchNamespace': ['example-*'],
                    'avoidNamespaces': [f'example-{i}' for i in range(5, USER_NAMESPACE_COUNT)]
                },
                'expected': [f'example-{i}' for i in range(5)],
            },
            {
                'name': 'avoid all user_namespaces',
                'body': {
                    'avoidNamespaces': ['example-*']
                },
                'expected': initial_namespaces,
            }
        ]

        for case in cases:
            self.assertListEqual(
                list1=sorted(case['expected']),
                list2=sorted(get_ns_list(
                    logger=logging.getLogger(__name__),
                    body=case['body'],
                    v1=mock_v1
                )),
                msg=case['name']
            )
