"""
AWS Secrets Manager utilities for fetching test secrets.

This module provides functions to fetch secrets from AWS Secrets Manager,
with support for AWS SSO authentication and fallback to environment variables.

Usage:
    from tests.utils import get_aws_secrets, get_secret_value
    from tests.utils.secret_names import SecretName, Environment

    # Fetch all secrets needed for your test in one call
    secrets = get_aws_secrets([SecretName.OPENAI_API_KEY, SecretName.COHERE_API_KEY])
    api_key = secrets[SecretName.OPENAI_API_KEY]

    # Fetch from deploy environment
    secrets = get_aws_secrets([SecretName.SOME_KEY], environment=Environment.DEPLOY)

    # Or fetch a single secret with fallback to env vars
    api_key = get_secret_value(SecretName.OPENAI_API_KEY)

Configuration via OS environment variables:
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

from tests.utils.secret_names import Environment
from tests.utils.secret_names import get_prefix_for_environment

logger = logging.getLogger(__name__)

# AWS Secrets Manager configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def get_aws_secrets(
    keys: list[str],
    environment: str = Environment.TEST,
) -> dict[str, str]:
    """
    Fetch secrets from AWS Secrets Manager in a single batch request.

    Uses the default boto3 credential chain, which includes:
    - OS environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - Shared credential file (~/.aws/credentials)
    - AWS SSO (if configured in ~/.aws/config and logged in via `aws sso login`)
    - IAM role (if running on EC2/ECS/Lambda)

    Args:
        keys: List of secret names to fetch. All are fetched in one API call.
        environment: The environment to fetch from (default: Environment.TEST).

    Returns:
        dict: Mapping of secret names to their values.
              Only includes successfully fetched secrets.

    Raises:
        RuntimeError: If secrets cannot be fetched due to auth/access issues.

    Example:
        from tests.utils.secret_names import SecretName, Environment

        # One API call fetches all secrets
        secrets = get_aws_secrets([
            SecretName.OPENAI_API_KEY,
            SecretName.COHERE_API_KEY,
        ])
    """
    if not keys:
        return {}

    prefix = get_prefix_for_environment(environment)

    session = boto3.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name=AWS_REGION,
    )

    secret_ids = [f"{prefix}{name}" for name in keys]

    try:
        # BatchGetSecretValue fetches up to 20 secrets in one request
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

    # Build result dict from response
    secrets: dict[str, str] = {}
    for secret in response.get("SecretValues", []):
        secret_id = secret.get("Name", "")
        secret_value = secret.get("SecretString")

        if secret_value:
            # Extract the key name by removing the prefix
            if secret_id.startswith(prefix):
                key_name = secret_id[len(prefix) :]
            else:
                key_name = secret_id
            secrets[key_name] = secret_value

    # Log any errors for individual secrets
    for error in response.get("Errors", []):
        secret_id = error.get("SecretId", "unknown")
        error_code = error.get("ErrorCode", "unknown")
        message = error.get("Message", "unknown error")
        logger.warning(
            f"Failed to fetch secret '{secret_id}': [{error_code}] {message}"
        )

    logger.info(
        f"Fetched {len(secrets)}/{len(keys)} secrets from AWS "
        f"(environment: {environment})"
    )

    return secrets


def get_secret_value(
    key: str,
    environment: str = Environment.TEST,
    required: bool = True,
) -> str | None:
    """
    Get a specific secret value, with fallback to OS environment variables.

    Useful for local development without AWS access.

    Args:
        key: The secret name (e.g., "OPENAI_API_KEY")
        environment: The environment to fetch from (default: Environment.TEST)
        required: If True, raises an error when the key is not found

    Returns:
        The secret value, or None if not found and not required

    Raises:
        RuntimeError: If required=True and the secret is not found
    """
    # First, check if there's an OS environment variable override
    env_value = os.environ.get(key)
    if env_value:
        logger.debug(f"Using OS environment variable for {key}")
        return env_value

    # Try to fetch from AWS Secrets Manager
    prefix = get_prefix_for_environment(environment)
    try:
        secrets = get_aws_secrets([key], environment=environment)
        value = secrets.get(key)
        if value:
            return value
    except RuntimeError as e:
        if required:
            logger.warning(f"Could not fetch from AWS Secrets Manager: {e}")
        else:
            logger.debug(f"AWS Secrets Manager not available, skipping {key}")

    if required:
        raise RuntimeError(
            f"Required secret '{key}' not found in AWS Secrets Manager "
            f"(looked for: {prefix}{key}) or OS environment variables."
        )

    return None


def check_secret_exists(
    key: str,
    environment: str = Environment.TEST,
) -> tuple[bool, str | None]:
    """
    Check if a secret exists in AWS Secrets Manager.

    Useful for validation tests that verify secrets are configured.

    Args:
        key: The secret name to check
        environment: The environment to check in (default: Environment.TEST)

    Returns:
        Tuple of (exists: bool, error_message: str | None)
    """
    session = boto3.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name=AWS_REGION,
    )

    prefix = get_prefix_for_environment(environment)
    secret_id = f"{prefix}{key}"

    try:
        client.get_secret_value(SecretId=secret_id)
        return True, None
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        message = e.response.get("Error", {}).get("Message", str(e))
        return False, f"[{error_code}] {message}"
