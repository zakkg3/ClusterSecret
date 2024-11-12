import datetime
import logging
import unittest
from typing import Tuple, Callable, Union
from unittest.mock import Mock

from kubernetes.client import V1ObjectMeta

from consts import CREATE_BY_ANNOTATION, LAST_SYNC_ANNOTATION, VERSION_ANNOTATION, BLOCKED_ANNOTATIONS, \
    CREATE_BY_AUTHOR, CLUSTER_SECRET_LABEL
from kubernetes_utils import get_ns_list, create_secret_metadata
from os_utils import get_version, get_blocked_labels

USER_NAMESPACE_COUNT = 10
initial_namespaces = ['default', 'kube-node-lease', 'kube-public', 'kube-system']
user_namespaces = [f'example-{index}' for index in range(USER_NAMESPACE_COUNT)]


def is_iso_format(date: str) -> bool:
    """check whether a date string parses correctly as ISO 8601 format"""
    try:
        datetime.datetime.fromisoformat(date)
        return True
    except (TypeError, ValueError):
        return False


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
                    'avoidNamespaces': ['example-*'],
                },
                'expected': initial_namespaces,
            },
        ]

        for case in cases:
            self.assertListEqual(
                list1=sorted(case['expected']),
                list2=sorted(get_ns_list(
                    logger=logging.getLogger(__name__),
                    body=case['body'],
                    v1=mock_v1,
                )),
                msg=case['name'],
            )

    def test_create_secret_metadata(self) -> None:

        expected_base_label_key = CLUSTER_SECRET_LABEL
        expected_base_label_value = 'true'

        # key, value pairs, where the value can be a string or validation function
        expected_base_annotations: list[Tuple[str, Union[str, Callable[[str], bool]]]] = [
            (CREATE_BY_ANNOTATION, CREATE_BY_AUTHOR),
            (VERSION_ANNOTATION, get_version()),
            # Since LAST_SYNC_ANNOTATION is a date string which isn't easily validated by string equality
            # have the function 'is_iso_format' validate the value of this annotation.
            (LAST_SYNC_ANNOTATION, is_iso_format)
        ]

        attributes_blocked_lists = dict(
            labels=get_blocked_labels(),
            annotations=BLOCKED_ANNOTATIONS,
        )

        test_cases: list[Tuple[dict[str, str], dict[str, str]]] = [
            # Annotations, Labels
            (
                {},
                {}
            ),
            (
                {},
                {"modifiedAt": "1692462880",
                 "name": "prometheus-operator",
                 "owner": "helm",
                 "status": "superseded",
                 "version": "1"}
            ),
            (
                {"managed-by": "argocd.argoproj.io"},
                {"argocd.argoproj.io/secret-type": "repository"}
            ),
            (
                {"argocd.argoproj.io/compare-options": "ServerSideDiff=true",
                 "argocd.argoproj.io/sync-wave": "4"},
                {"app.kubernetes.io/instance": "cluster-secret"}
            )
        ]

        for annotations, labels in test_cases:

            subject: V1ObjectMeta = create_secret_metadata(
                name='test_secret',
                namespace='test_namespace',
                annotations=annotations,
                labels=labels
            )

            self.assertIsInstance(obj=subject, cls=V1ObjectMeta, msg='returned value has correct type')

            for attribute, blocked_list in attributes_blocked_lists.items():
                attribute_object = subject.__getattribute__(attribute)
                self.assertIsNotNone(obj=attribute_object, msg=f'attribute "{attribute}" is not None')

                for key in attribute_object.keys():
                    self.assertIsInstance(obj=key, cls=str, msg=f'the {attribute} key is a string')
                    for blocked_listed_label_prefix in blocked_list:
                        self.assertFalse(
                            expr=key.startswith(blocked_listed_label_prefix),
                            msg=f'{attribute} key does not match black listed prefix'
                        )

            # This tells mypy that those attributes are not None
            assert subject.labels is not None
            assert subject.annotations is not None

            self.assertEqual(
                first=subject.labels[expected_base_label_key],
                second=expected_base_label_value,
                msg='expected base label is present'
            )
            for key, value_expectation in expected_base_annotations:
                validator = value_expectation if callable(value_expectation) else value_expectation.__eq__
                value = subject.annotations[key]
                self.assertTrue(
                    expr=validator(value),
                    msg=f'expected base annotation with key {key} is present and its value {value} is as expected'
                )
