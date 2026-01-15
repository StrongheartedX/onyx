"""
Secret name and environment constants.

Usage:
    from tests.utils import SecretName, Environment, get_aws_secrets

    secrets = get_aws_secrets(
        [SecretName.OPENAI_API_KEY, SecretName.COHERE_API_KEY],
        environment=Environment.TEST,
    )
"""


class Environment:
    """
    Constants for secret environments.

    Environments allow the same logical secret name to have different
    values and permissions in different contexts.
    """

    TEST = "test"
    DEPLOY = "deploy"


class SecretName:
    """
    Constants for secret names.

    Use these constants when requesting secrets to avoid typos and enable
    IDE autocompletion.
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
