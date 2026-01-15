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

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.utils import check_secret_exists
from tests.utils import Environment
from tests.utils import SecretName


def _load_secrets_yaml() -> dict[str, Any]:
    """Load the secrets configuration from YAML."""
    yaml_path = Path(__file__).parent / "secrets.yaml"
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def _get_all_secrets_with_environments() -> list[tuple[str, str, str]]:
    """
    Get all (environment, secret_name, prefix) tuples for parametrized testing.
    """
    config = _load_secrets_yaml()
    results = []
    for env_name, env_config in config.get("environments", {}).items():
        prefix = env_config.get("prefix", f"onyx/{env_name}/")
        secrets = env_config.get("secrets", []) or []
        for secret in secrets:
            results.append((env_name, secret["name"], prefix))
    return results


@pytest.mark.parametrize(
    "environment,secret_name,prefix",
    _get_all_secrets_with_environments(),
    ids=lambda p: f"{p[0]}-{p[1]}" if isinstance(p, tuple) else str(p),
)
def test_secret_exists(environment: str, secret_name: str, prefix: str) -> None:
    """
    Verify that each defined secret exists in AWS Secrets Manager.

    This test is parametrized to run once for each secret defined in secrets.yaml,
    across all environments.
    """
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


def test_yaml_secrets_have_constants() -> None:
    """
    Verify that all secrets in YAML have corresponding SecretName constants.
    """
    config = _load_secrets_yaml()

    # Get all string attributes from SecretName
    constant_values = {
        v
        for k, v in vars(SecretName).items()
        if not k.startswith("_") and isinstance(v, str)
    }

    # Get all unique secret names from YAML
    yaml_names: set[str] = set()
    for env_config in config.get("environments", {}).values():
        secrets = env_config.get("secrets", []) or []
        for secret in secrets:
            yaml_names.add(secret["name"])

    missing = yaml_names - constant_values
    assert not missing, (
        f"Secrets in secrets.yaml missing from SecretName class: {missing}\n"
        f"Add these constants to SecretName in secret_names.py"
    )


def test_yaml_environments_have_constants() -> None:
    """
    Verify that all environments in YAML have corresponding Environment constants.
    """
    config = _load_secrets_yaml()

    # Get environment constants from class
    constant_values = {
        v
        for k, v in vars(Environment).items()
        if not k.startswith("_") and isinstance(v, str)
    }

    yaml_environments = set(config.get("environments", {}).keys())

    missing_from_constants = yaml_environments - constant_values
    assert not missing_from_constants, (
        f"Environments in secrets.yaml missing from Environment class: "
        f"{missing_from_constants}\n"
        f"Add these constants to Environment in secret_names.py"
    )

    missing_from_yaml = constant_values - yaml_environments
    assert not missing_from_yaml, (
        f"Environment constants not defined in secrets.yaml: {missing_from_yaml}\n"
        f"Add these environments to secrets.yaml"
    )
