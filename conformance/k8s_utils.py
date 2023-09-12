import time
from kubernetes import client, config
from kubernetes.client.rest import ApiException


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

