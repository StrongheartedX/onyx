"""
Secret name constants and namespace configuration.

This module loads secret definitions from secrets.yaml and provides
type-safe constants for use in tests and deployment scripts.

Usage:
    from tests.utils.secret_names import SecretName, Namespace
    from tests.utils import get_aws_secrets

    # For tests (default namespace)
    secrets = get_aws_secrets([SecretName.OPENAI_API_KEY])

    # For deployment scripts
    secrets = get_aws_secrets([SecretName.SOME_KEY], namespace=Namespace.DEPLOY)
"""

from pathlib import Path
from typing import Any

import yaml


def _load_secrets_config() -> dict[str, Any]:
    """Load the full secrets configuration from YAML."""
    yaml_path = Path(__file__).parent / "secrets.yaml"
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def _get_namespace_config(namespace: str) -> dict[str, Any]:
    """Get configuration for a specific namespace."""
    config = _load_secrets_config()
    namespaces = config.get("namespaces", {})
    if namespace not in namespaces:
        raise ValueError(
            f"Unknown namespace '{namespace}'. "
            f"Available namespaces: {list(namespaces.keys())}"
        )
    return namespaces[namespace]


def get_secret_names_for_namespace(namespace: str) -> list[str]:
    """Get all secret names defined for a namespace."""
    ns_config = _get_namespace_config(namespace)
    secrets = ns_config.get("secrets", [])
    # Handle empty list represented as [] in YAML
    if secrets is None:
        return []
    return [secret["name"] for secret in secrets]


def get_prefix_for_namespace(namespace: str) -> str:
    """Get the AWS secret prefix for a namespace."""
    ns_config = _get_namespace_config(namespace)
    return ns_config.get("prefix", f"onyx/{namespace}/")


def get_all_namespaces() -> list[str]:
    """Get all available namespace names."""
    config = _load_secrets_config()
    return list(config.get("namespaces", {}).keys())


class Namespace:
    """
    Constants for secret namespaces.

    Namespaces allow the same logical secret name to have different
    values and permissions in different contexts.

    Example:
        # Test namespace (default) - read-only credentials
        secrets = get_aws_secrets([SecretName.API_KEY])

        # Deploy namespace - elevated permissions
        secrets = get_aws_secrets([SecretName.API_KEY], namespace=Namespace.DEPLOY)
    """

    TEST = "test"
    DEPLOY = "deploy"


class SecretName:
    """
    Constants for secret names.

    Use these constants when requesting secrets to avoid typos and enable
    IDE autocompletion. The same constant can be used across different
    namespaces.

    Example:
        # Fetch from test namespace (default)
        secrets = get_aws_secrets([SecretName.OPENAI_API_KEY])

        # Fetch from deploy namespace
        secrets = get_aws_secrets(
            [SecretName.DOCKER_REGISTRY_PASSWORD],
            namespace=Namespace.DEPLOY
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
    # When adding, also add to the appropriate namespace in secrets.yaml
