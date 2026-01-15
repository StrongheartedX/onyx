"""
Secret name constants and environment configuration.

This module loads secret definitions from secrets.yaml and provides
type-safe constants for use in tests and deployment scripts.

Usage:
    from tests.utils.secret_names import SecretName, Environment
    from tests.utils import get_aws_secrets

    # For tests (default environment)
    secrets = get_aws_secrets([SecretName.OPENAI_API_KEY])

    # For deployment scripts
    secrets = get_aws_secrets([SecretName.SOME_KEY], environment=Environment.DEPLOY)
"""

from pathlib import Path
from typing import Any

import yaml


def _load_secrets_config() -> dict[str, Any]:
    """Load the full secrets configuration from YAML."""
    yaml_path = Path(__file__).parent / "secrets.yaml"
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def _get_environment_config(environment: str) -> dict[str, Any]:
    """Get configuration for a specific environment."""
    config = _load_secrets_config()
    environments = config.get("environments", {})
    if environment not in environments:
        raise ValueError(
            f"Unknown environment '{environment}'. "
            f"Available environments: {list(environments.keys())}"
        )
    return environments[environment]


def get_secret_names_for_environment(environment: str) -> list[str]:
    """Get all secret names defined for an environment."""
    env_config = _get_environment_config(environment)
    secrets = env_config.get("secrets", [])
    # Handle empty list represented as [] in YAML
    if secrets is None:
        return []
    return [secret["name"] for secret in secrets]


def get_prefix_for_environment(environment: str) -> str:
    """Get the AWS secret prefix for an environment."""
    env_config = _get_environment_config(environment)
    return env_config.get("prefix", f"onyx/{environment}/")


def get_all_environments() -> list[str]:
    """Get all available environment names."""
    config = _load_secrets_config()
    return list(config.get("environments", {}).keys())


class Environment:
    """
    Constants for secret environments.

    Environments allow the same logical secret name to have different
    values and permissions in different contexts.

    Example:
        # Test environment (default) - read-only credentials
        secrets = get_aws_secrets([SecretName.API_KEY])

        # Deploy environment - elevated permissions
        secrets = get_aws_secrets([SecretName.API_KEY], environment=Environment.DEPLOY)
    """

    TEST = "test"
    DEPLOY = "deploy"


class SecretName:
    """
    Constants for secret names.

    Use these constants when requesting secrets to avoid typos and enable
    IDE autocompletion. The same constant can be used across different
    environments.

    Example:
        # Fetch from test environment (default)
        secrets = get_aws_secrets([SecretName.OPENAI_API_KEY])

        # Fetch from deploy environment
        secrets = get_aws_secrets(
            [SecretName.DOCKER_REGISTRY_PASSWORD],
            environment=Environment.DEPLOY
        )
    """

    # OpenAI
    OPENAI_API_KEY = "OPENAI_API_KEY"

    # Cohere
    COHERE_API_KEY = "COHERE_API_KEY"

    # Azure OpenAI
    AZURE_API_KEY = "AZURE_API_KEY"
    AZURE_API_URL = "AZURE_API_URL"

    # LiteLLM
    LITELLM_API_KEY = "LITELLM_API_KEY"
    LITELLM_API_URL = "LITELLM_API_URL"

    # Add new secret constants here as needed
    # When adding, also add to the appropriate environment in secrets.yaml
