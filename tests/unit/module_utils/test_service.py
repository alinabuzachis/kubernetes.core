from unittest.mock import Mock

import pytest
from kubernetes.dynamic.resource import ResourceInstance

from ansible_collections.kubernetes.core.plugins.module_utils.k8s.service import (
    K8sService,
)

from kubernetes.dynamic.exceptions import (
    NotFoundError,
    ForbiddenError,
)

pod_definition = {
    "apiVersion": "v1",
    "kind": "Pod",
    "metadata": {
        "name": "foo",
        "labels": {"environment": "production", "app": "nginx"},
        "namespace": "foo",
    },
    "spec": {
        "containers": [
            {
                "name": "nginx",
                "image": "nginx:1.14.2",
                "command": ["/bin/sh", "-c", "sleep 10"],
            }
        ]
    },
}

pod_definition_updated = {
    "apiVersion": "v1",
    "kind": "Pod",
    "metadata": {
        "name": "foo",
        "labels": {"environment": "testing", "app": "nginx"},
        "namespace": "bar",
    },
    "spec": {
        "containers": [
            {
                "name": "nginx",
                "image": "nginx:1.14.2",
                "command": ["/bin/sh", "-c", "sleep 10"],
            }
        ]
    },
}


@pytest.fixture(scope="module")
def mock_pod_resource_instance():
    return ResourceInstance(None, pod_definition)


@pytest.fixture(scope="module")
def mock_pod_updated_resource_instance():
    return ResourceInstance(None, pod_definition_updated)


def test_diff_objects_no_diff():
    svc = K8sService(Mock(), Mock(), Mock())
    match, diff = svc.diff_objects(pod_definition, pod_definition)

    assert match is True
    assert diff == {}


def test_diff_objects_meta_diff():
    svc = K8sService(Mock(), Mock(), Mock())
    match, diff = svc.diff_objects(pod_definition, pod_definition_updated)

    assert match is False
    assert diff["before"] == {
        "metadata": {"labels": {"environment": "production"}, "namespace": "foo"}
    }
    assert diff["after"] == {
        "metadata": {"labels": {"environment": "testing"}, "namespace": "bar"}
    }


def test_diff_objects_spec_diff():
    pod_definition_updated = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "foo",
            "labels": {"environment": "production", "app": "nginx"},
            "namespace": "foo",
        },
        "spec": {
            "containers": [
                {
                    "name": "busybox",
                    "image": "busybox",
                    "command": ["/bin/sh", "-c", "sleep 3600"],
                }
            ]
        },
    }
    svc = K8sService(Mock(), Mock(), Mock())
    match, diff = svc.diff_objects(pod_definition, pod_definition_updated)

    assert match is False
    assert diff["before"]["spec"] == pod_definition["spec"]
    assert diff["after"]["spec"] == pod_definition_updated["spec"]


def test_service_delete_existing_resource(mock_pod_resource_instance):
    spec = {"delete.side_effect": [mock_pod_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.delete(Mock(), pod_definition, mock_pod_resource_instance)

    assert isinstance(results, dict)
    assert results["changed"] is True
    assert results["result"] == pod_definition


def test_service_delete_no_existing_resource():
    module = Mock()
    module.params = {}
    module.check_mode = False
    svc = K8sService(Mock(), module, Mock())
    results = svc.delete(Mock(), pod_definition)

    assert isinstance(results, dict)
    assert results["changed"] is False
    assert results["result"] == {}


def test_service_delete_existing_resource_check_mode(mock_pod_resource_instance):
    module = Mock()
    module.params = {"wait": False}
    module.check_mode = True
    svc = K8sService(Mock(), module, Mock())
    results = svc.delete(Mock(), pod_definition, mock_pod_resource_instance)

    assert isinstance(results, dict)
    assert results["changed"] is True


def test_service_create_resource(mock_pod_resource_instance):
    spec = {"create.side_effect": [mock_pod_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.create(Mock(), pod_definition)

    assert isinstance(results, dict)
    assert results["changed"] is True
    assert results["result"] == pod_definition


def test_service_create_resource_failed():
    spec = {"create.side_effect": [Exception(Mock())]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.create(Mock(), pod_definition)

    assert isinstance(results, dict)
    assert results["changed"] is False
    assert results["result"] == {}
    assert "Failed to create object" in results["error"]["msg"]


def test_service_create_resource_check_mode():
    client = Mock()
    client.dry_run = False
    module = Mock()
    module.params = {}
    module.check_mode = True
    svc = K8sService(client, module, Mock())
    results = svc.create(Mock(), pod_definition)

    assert isinstance(results, dict)
    assert results["changed"] is True
    assert results["result"] == pod_definition


def test_service_retrieve_existing_resource(mock_pod_resource_instance):
    spec = {"get.side_effect": [mock_pod_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    svc = K8sService(client, module, Mock())
    results = svc.retrieve(Mock(), pod_definition)

    assert isinstance(results, dict)
    assert results["changed"] is False
    assert results["result"] == pod_definition


def test_service_retrieve_no_existing_resource():
    spec = {"get.side_effect": [NotFoundError(Mock())]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    svc = K8sService(client, module, Mock())
    results = svc.retrieve(Mock(), pod_definition)

    assert isinstance(results, dict)
    assert results["changed"] is False
    assert results["result"] == {}


def test_service_retrieve_existing_error():
    spec = {"get.side_effect": [ForbiddenError(Mock())]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    svc = K8sService(client, module, Mock())
    results = svc.retrieve(Mock(), pod_definition)

    assert isinstance(results, dict)
    assert results["changed"] is False
    assert results["result"] == {}
    assert "Failed to retrieve requested object" in results["error"]["msg"]


def test_create_project_request():
    project_definition = {
        "apiVersion": "v1",
        "kind": "ProjectRequest",
        "metadata": {"name": "test"},
    }
    spec = {"create.side_effect": [ResourceInstance(None, project_definition)]}
    client = Mock(**spec)
    module = Mock()
    module.check_mode = False
    module.params = {"state": "present"}
    svc = K8sService(client, module, Mock())
    results = svc.create_project_request(project_definition)

    assert isinstance(results, dict)
    assert results["changed"] is True
    assert results["result"] == project_definition


def test_service_apply_existing_resource(mock_pod_resource_instance, mock_pod_updated_resource_instance):
    spec = {"apply.side_effect": [mock_pod_updated_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {"apply": True}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.apply(Mock(), pod_definition_updated, mock_pod_resource_instance)

    assert isinstance(results, dict)
    assert results["changed"] is True
    assert results["diff"] is not {}
    assert results["result"] == pod_definition_updated


def test_service_apply_existing_resource_no_diff(mock_pod_resource_instance):
    spec = {"apply.side_effect": [mock_pod_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {"apply": True}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.apply(Mock(), pod_definition, mock_pod_resource_instance)

    assert isinstance(results, dict)
    assert results["changed"] is False
    assert results["diff"] == {}
    assert results["result"] == pod_definition


def test_service_apply_existing_resource_no_apply(mock_pod_resource_instance):
    spec = {"apply.side_effect": [mock_pod_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {"apply": False}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.apply(Mock(), pod_definition, mock_pod_resource_instance)

    assert isinstance(results, dict)
    assert results["changed"] is False
    assert results["result"] == {}


def test_service_replace_existing_resource_no_diff(mock_pod_resource_instance):
    spec = {"replace.side_effect": [mock_pod_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.replace(Mock(), pod_definition, mock_pod_resource_instance)

    assert isinstance(results, dict)
    assert results["changed"] is False
    assert results["diff"] == {}
    assert results["result"] == pod_definition


def test_service_replace_existing_resource_(
    mock_pod_resource_instance, mock_pod_updated_resource_instance
):
    spec = {"replace.side_effect": [mock_pod_updated_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.replace(Mock(), pod_definition_updated, mock_pod_resource_instance)

    assert isinstance(results, dict)
    assert results["changed"] is True
    assert results["result"] == pod_definition_updated
    assert results["diff"] != {}
    assert results["diff"]["before"] is not {}
    assert results["diff"]["after"] is not {}


def test_service_update_existing_resource(
    mock_pod_resource_instance, mock_pod_updated_resource_instance
):
    spec = {"replace.side_effect": [mock_pod_updated_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.replace(Mock(), pod_definition_updated, mock_pod_resource_instance)

    assert isinstance(results, dict)
    assert results["changed"] is True
    assert results["result"] == pod_definition_updated
    assert results["diff"] != {}
    assert results["diff"]["before"] is not {}
    assert results["diff"]["after"] is not {}


def test_service_update_existing_resource_no_diff(mock_pod_updated_resource_instance):
    spec = {"replace.side_effect": [mock_pod_updated_resource_instance]}
    client = Mock(**spec)
    module = Mock()
    module.params = {}
    module.check_mode = False
    svc = K8sService(client, module, Mock())
    results = svc.replace(
        Mock(), pod_definition_updated, mock_pod_updated_resource_instance
    )

    assert isinstance(results, dict)
    assert results["changed"] is False
    assert results["result"] == pod_definition_updated
    assert results["diff"] == {}
