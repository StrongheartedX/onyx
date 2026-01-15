"""
Validation tests for AWS Secrets Manager configuration.

These tests verify that all secrets defined in secrets.yaml actually exist
in AWS Secrets Manager. Run these tests to validate your AWS setup before
running the full test suite.

Usage:
    # Check all secrets in all namespaces
    pytest backend/tests/utils/test_secrets_exist.py -v

    # Check only test namespace secrets
    pytest backend/tests/utils/test_secrets_exist.py -v -k "test-"
"""

import pytest

from tests.utils import check_secret_exists
from tests.utils import get_all_namespaces
from tests.utils import get_prefix_for_namespace
from tests.utils import get_secret_names_for_namespace
from tests.utils import Namespace
from tests.utils.secret_names import SecretName


def _get_all_secrets_with_namespaces() -> list[tuple[str, str]]:
    """Get all (namespace, secret_name) pairs for parametrized testing."""
    pairs = []
    for namespace in get_all_namespaces():
        for secret_name in get_secret_names_for_namespace(namespace):
            pairs.append((namespace, secret_name))
    return pairs


# Generate test IDs like "test-OPENAI_API_KEY", "deploy-DOCKER_PASSWORD"
def _make_test_id(param: tuple[str, str]) -> str:
    namespace, secret_name = param
    return f"{namespace}-{secret_name}"


@pytest.mark.parametrize(
    "namespace,secret_name",
    _get_all_secrets_with_namespaces(),
    ids=lambda p: _make_test_id(p) if isinstance(p, tuple) else str(p),
)
def test_secret_exists(namespace: str, secret_name: str) -> None:
    """
    Verify that each defined secret exists in AWS Secrets Manager.

    This test is parametrized to run once for each secret defined in secrets.yaml,
    across all namespaces. It helps catch configuration issues early, such as:
    - Missing secrets
    - Typos in secret names
    - Permission issues for specific secrets
    """
    prefix = get_prefix_for_namespace(namespace)
    exists, error = check_secret_exists(secret_name, namespace=namespace)
    assert exists, (
        f"Secret '{secret_name}' not found in namespace '{namespace}'.\n"
        f"Expected secret ID: {prefix}{secret_name}\n"
        f"Error: {error}\n\n"
        f"To create this secret, run:\n"
        f"  aws secretsmanager create-secret "
        f'--name "{prefix}{secret_name}" '
        f'--secret-string "your-secret-value"'
    )


def test_yaml_and_constants_in_sync() -> None:
    """
    Verify that secrets.yaml and SecretName class are in sync.

    This ensures that when new secrets are added to the YAML file,
    corresponding constants are also added to the SecretName class.
    """
    # Get all string attributes from SecretName (excluding private/dunder)
    constant_values = {
        v
        for k, v in vars(SecretName).items()
        if not k.startswith("_") and isinstance(v, str)
    }

    # Get all unique secret names from all namespaces in YAML
    yaml_names: set[str] = set()
    for namespace in get_all_namespaces():
        yaml_names.update(get_secret_names_for_namespace(namespace))

    # Check for secrets in YAML but not in constants
    missing_from_constants = yaml_names - constant_values
    assert not missing_from_constants, (
        f"Secrets defined in secrets.yaml but missing from SecretName class: "
        f"{missing_from_constants}\n"
        f"Please add these constants to SecretName in secret_names.py"
    )

    # Note: We don't check for constants not in YAML because a constant might
    # be defined for future use or for a namespace not yet configured


def test_namespace_constants_match_yaml() -> None:
    """
    Verify that Namespace class constants match namespaces defined in YAML.
    """
    # Get namespace constants from class
    namespace_constants = {
        v
        for k, v in vars(Namespace).items()
        if not k.startswith("_") and isinstance(v, str)
    }

    # Get namespaces from YAML
    yaml_namespaces = set(get_all_namespaces())

    # Check for namespaces in YAML but not in constants
    missing_from_constants = yaml_namespaces - namespace_constants
    assert not missing_from_constants, (
        f"Namespaces defined in secrets.yaml but missing from Namespace class: "
        f"{missing_from_constants}\n"
        f"Please add these constants to Namespace in secret_names.py"
    )

    # Check for constants not in YAML
    missing_from_yaml = namespace_constants - yaml_namespaces
    assert not missing_from_yaml, (
        f"Constants in Namespace class but not defined in secrets.yaml: "
        f"{missing_from_yaml}\n"
        f"Please add these namespaces to secrets.yaml"
    )
