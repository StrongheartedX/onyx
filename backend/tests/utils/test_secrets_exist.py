"""
Validation tests for AWS Secrets Manager configuration.

These tests verify that all secrets defined in secrets.yaml actually exist
in AWS Secrets Manager. Run these tests to validate your AWS setup before
running the full test suite.

Usage:
    # Check all secrets in all environments
    pytest backend/tests/utils/test_secrets_exist.py -v

    # Check only test environment secrets
    pytest backend/tests/utils/test_secrets_exist.py -v -k "test-"
"""

import pytest

from tests.utils import check_secret_exists
from tests.utils import Environment
from tests.utils import get_all_environments
from tests.utils import get_prefix_for_environment
from tests.utils import get_secret_names_for_environment
from tests.utils.secret_names import SecretName


def _get_all_secrets_with_environments() -> list[tuple[str, str]]:
    """Get all (environment, secret_name) pairs for parametrized testing."""
    pairs = []
    for environment in get_all_environments():
        for secret_name in get_secret_names_for_environment(environment):
            pairs.append((environment, secret_name))
    return pairs


# Generate test IDs like "test-OPENAI_API_KEY", "deploy-DOCKER_PASSWORD"
def _make_test_id(param: tuple[str, str]) -> str:
    environment, secret_name = param
    return f"{environment}-{secret_name}"


@pytest.mark.parametrize(
    "environment,secret_name",
    _get_all_secrets_with_environments(),
    ids=lambda p: _make_test_id(p) if isinstance(p, tuple) else str(p),
)
def test_secret_exists(environment: str, secret_name: str) -> None:
    """
    Verify that each defined secret exists in AWS Secrets Manager.

    This test is parametrized to run once for each secret defined in secrets.yaml,
    across all environments. It helps catch configuration issues early, such as:
    - Missing secrets
    - Typos in secret names
    - Permission issues for specific secrets
    """
    prefix = get_prefix_for_environment(environment)
    exists, error = check_secret_exists(secret_name, environment=environment)
    assert exists, (
        f"Secret '{secret_name}' not found in environment '{environment}'.\n"
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

    # Get all unique secret names from all environments in YAML
    yaml_names: set[str] = set()
    for environment in get_all_environments():
        yaml_names.update(get_secret_names_for_environment(environment))

    # Check for secrets in YAML but not in constants
    missing_from_constants = yaml_names - constant_values
    assert not missing_from_constants, (
        f"Secrets defined in secrets.yaml but missing from SecretName class: "
        f"{missing_from_constants}\n"
        f"Please add these constants to SecretName in secret_names.py"
    )

    # Note: We don't check for constants not in YAML because a constant might
    # be defined for future use or for an environment not yet configured


def test_environment_constants_match_yaml() -> None:
    """
    Verify that Environment class constants match environments defined in YAML.
    """
    # Get environment constants from class
    environment_constants = {
        v
        for k, v in vars(Environment).items()
        if not k.startswith("_") and isinstance(v, str)
    }

    # Get environments from YAML
    yaml_environments = set(get_all_environments())

    # Check for environments in YAML but not in constants
    missing_from_constants = yaml_environments - environment_constants
    assert not missing_from_constants, (
        f"Environments defined in secrets.yaml but missing from Environment class: "
        f"{missing_from_constants}\n"
        f"Please add these constants to Environment in secret_names.py"
    )

    # Check for constants not in YAML
    missing_from_yaml = environment_constants - yaml_environments
    assert not missing_from_yaml, (
        f"Constants in Environment class but not defined in secrets.yaml: "
        f"{missing_from_yaml}\n"
        f"Please add these environments to secrets.yaml"
    )
