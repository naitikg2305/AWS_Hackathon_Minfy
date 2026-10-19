import os

from strands.models.bedrock import BedrockModel

# Validated with Sonnet 4.5 (20/20 labeled events). Override via MODEL_ID env var,
# e.g. us.anthropic.claude-haiku-4-5-20251001-v1:0 for a ~3x cheaper run.
DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


def load_model() -> BedrockModel:
    """Get Bedrock model client using the runtime's IAM execution role."""
    model_id = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    return BedrockModel(
        model_id=model_id,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
