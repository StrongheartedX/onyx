"""
AWS Secrets Manager utilities for fetching test secrets.

This module provides functions to fetch secrets from AWS Secrets Manager,
with support for AWS SSO authentication and fallback to environment variables.

Usage:
    from tests.utils import get_aws_secrets, get_secret_value
    from tests.utils.secret_names import SecretName, Namespace

    # Fetch specific secrets from test namespace (default)
    secrets = get_aws_secrets([SecretName.OPENAI_API_KEY, SecretName.COHERE_API_KEY])
    api_key = secrets[SecretName.OPENAI_API_KEY]

    # Fetch from deploy namespace
    secrets = get_aws_secrets([SecretName.SOME_KEY], namespace=Namespace.DEPLOY)

    # Or fetch a single secret with fallback to env vars
    api_key = get_secret_value(SecretName.OPENAI_API_KEY)

Configuration via environment variables:
    - AWS_REGION: AWS region for Secrets Manager (default: "us-east-1")
    - AWS_PROFILE: (Optional) AWS profile to use for SSO authentication

AWS SSO Authentication:
    boto3 automatically uses SSO credentials if configured in ~/.aws/config.
    Run `aws sso login` to authenticate before running tests.
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

from tests.utils.secret_names import get_prefix_for_namespace
from tests.utils.secret_names import Namespace

logger = logging.getLogger(__name__)

# AWS Secrets Manager configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Cache for fetched secrets, keyed by (namespace, secret_name)
_secrets_cache: dict[tuple[str, str], str] = {}


def get_aws_secrets(
    keys: list[str],
    namespace: str = Namespace.TEST,
) -> dict[str, str]:
    """
    Fetch specified secrets from AWS Secrets Manager in a single batch request.

    Uses the default boto3 credential chain, which includes:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - Shared credential file (~/.aws/credentials)
    - AWS SSO (if configured in ~/.aws/config and logged in via `aws sso login`)
    - IAM role (if running on EC2/ECS/Lambda)

    Each secret should be stored as a separate secret in AWS Secrets Manager
    with a plaintext value (not JSON). For example:
        - onyx/test/OPENAI_API_KEY -> "sk-..."
        - onyx/deploy/DOCKER_PASSWORD -> "..."

    Args:
        keys: List of secret names to fetch (e.g., ["OPENAI_API_KEY", "COHERE_API_KEY"])
        namespace: The namespace to fetch from (default: Namespace.TEST)
                   Different namespaces can have different values for the same key.

    Returns:
        dict: Mapping of secret names to their values (only includes successfully fetched secrets)

    Raises:
        RuntimeError: If secrets cannot be fetched due to auth/access issues

    Example:
        from tests.utils.secret_names import SecretName, Namespace

        # Test secrets (default)
        secrets = get_aws_secrets([SecretName.OPENAI_API_KEY])

        # Deploy secrets (elevated permissions)
        secrets = get_aws_secrets([SecretName.SOME_KEY], namespace=Namespace.DEPLOY)
    """
    if not keys:
        return {}

    prefix = get_prefix_for_namespace(namespace)

    # Check which keys we already have cached for this namespace
    uncached_keys = [k for k in keys if (namespace, k) not in _secrets_cache]

    # If all keys are cached, return from cache
    if not uncached_keys:
        return {
            k: _secrets_cache[(namespace, k)]
            for k in keys
            if (namespace, k) in _secrets_cache
        }

    # Create a session that will use SSO credentials if configured
    session = boto3.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name=AWS_REGION,
    )

    # Build the list of secret IDs to fetch (only uncached ones)
    secret_ids = [f"{prefix}{name}" for name in uncached_keys]

    try:
        # BatchGetSecretValue can fetch up to 20 secrets in one request
        response = client.batch_get_secret_value(SecretIdList=secret_ids)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "AccessDeniedException":
            raise RuntimeError(
                f"Access denied to secrets with prefix '{prefix}'. "
                f"Please check your AWS credentials/permissions or run 'aws sso login'."
            ) from e
        elif error_code == "UnrecognizedClientException":
            raise RuntimeError(
                "AWS credentials not found or expired. "
                "If using SSO, run 'aws sso login' to authenticate."
            ) from e
        else:
            raise RuntimeError(
                f"Failed to fetch secrets from AWS Secrets Manager: {e}"
            ) from e

    # Process successfully fetched secrets and add to cache
    for secret in response.get("SecretValues", []):
        secret_id = secret.get("Name", "")
        secret_value = secret.get("SecretString")

        if secret_value:
            # Extract the key name by removing the prefix
            if secret_id.startswith(prefix):
                key_name = secret_id[len(prefix) :]
            else:
                key_name = secret_id
            _secrets_cache[(namespace, key_name)] = secret_value

    # Log any errors for individual secrets
    for error in response.get("Errors", []):
        secret_id = error.get("SecretId", "unknown")
        error_code = error.get("ErrorCode", "unknown")
        message = error.get("Message", "unknown error")
        logger.warning(
            f"Failed to fetch secret '{secret_id}': [{error_code}] {message}"
        )

    fetched_count = sum(1 for k in uncached_keys if (namespace, k) in _secrets_cache)
    logger.info(
        f"Fetched {fetched_count}/{len(uncached_keys)} secrets "
        f"from AWS Secrets Manager (namespace: {namespace}, prefix: {prefix})"
    )

    # Return only the requested keys that we have
    return {
        k: _secrets_cache[(namespace, k)]
        for k in keys
        if (namespace, k) in _secrets_cache
    }


def get_secret_value(
    key: str,
    namespace: str = Namespace.TEST,
    required: bool = True,
) -> str | None:
    """
    Get a specific secret value from AWS Secrets Manager.

    Falls back to environment variables if AWS secrets are not available,
    allowing local development without AWS access.

    Args:
        key: The secret name (e.g., "OPENAI_API_KEY")
        namespace: The namespace to fetch from (default: Namespace.TEST)
        required: If True, raises an error when the key is not found

    Returns:
        The secret value, or None if not found and not required

    Raises:
        RuntimeError: If required=True and the secret is not found

    Example:
        from tests.utils.secret_names import SecretName, Namespace

        api_key = get_secret_value(SecretName.OPENAI_API_KEY)
        deploy_key = get_secret_value(SecretName.SOME_KEY, namespace=Namespace.DEPLOY)
    """
    # First, check if there's an environment variable override
    env_value = os.environ.get(key)
    if env_value:
        logger.debug(f"Using environment variable for {key}")
        return env_value

    # Try to fetch from AWS Secrets Manager
    prefix = get_prefix_for_namespace(namespace)
    try:
        secrets = get_aws_secrets([key], namespace=namespace)
        value = secrets.get(key)
        if value:
            return value
    except RuntimeError as e:
        if required:
            # Log the AWS error but continue to check if we should fail
            logger.warning(f"Could not fetch from AWS Secrets Manager: {e}")
        else:
            logger.debug(f"AWS Secrets Manager not available, skipping {key}")

    if required:
        raise RuntimeError(
            f"Required secret '{key}' not found in AWS Secrets Manager "
            f"(looked for: {prefix}{key}) or environment variables."
        )

    return None


def check_secret_exists(
    key: str,
    namespace: str = Namespace.TEST,
) -> tuple[bool, str | None]:
    """
    Check if a secret exists in AWS Secrets Manager.

    This is useful for validation tests that verify all expected secrets are configured.

    Args:
        key: The secret name to check
        namespace: The namespace to check in (default: Namespace.TEST)

    Returns:
        Tuple of (exists: bool, error_message: str | None)

    Example:
        exists, error = check_secret_exists(SecretName.OPENAI_API_KEY)
        assert exists, f"Secret missing: {error}"
    """
    session = boto3.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name=AWS_REGION,
    )

    prefix = get_prefix_for_namespace(namespace)
    secret_id = f"{prefix}{key}"

    try:
        client.get_secret_value(SecretId=secret_id)
        return True, None
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        message = e.response.get("Error", {}).get("Message", str(e))
        return False, f"[{error_code}] {message}"


def clear_secrets_cache() -> None:
    """Clear the secrets cache. Useful for testing."""
    _secrets_cache.clear()
