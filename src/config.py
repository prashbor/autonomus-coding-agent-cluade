"""Configuration for the autonomous coding agent."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Available Claude models on AWS Bedrock (cross-region inference)
# Pricing source: AWS Bedrock Pricing page (Global Cross-region Inference)
class BedrockModels:
    """Available Claude model IDs for AWS Bedrock."""

    OPUS_4_6 = "us.anthropic.claude-opus-4-6-v1"
    OPUS_4_5 = "us.anthropic.claude-opus-4-5-20251101-v1:0"
    SONNET_4_5 = "us.anthropic.claude-sonnet-4-5-20250514-v1:0"
    SONNET_4 = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    HAIKU_4_5 = "us.anthropic.claude-haiku-4-5-20250514-v1:0"


@dataclass
class BedrockConfig:
    """AWS Bedrock configuration."""

    # AWS Region (default: us-east-1)
    region: str = os.getenv("AWS_REGION", "us-east-1")

    # Bedrock model ID
    # Use BedrockModels constants or set via environment variable
    # Default: Claude Opus 4.6 (most capable model)
    # For faster/cheaper tasks: set BEDROCK_MODEL_ID to BedrockModels.SONNET_4
    model_id: str = os.getenv(
        "BEDROCK_MODEL_ID",
        BedrockModels.OPUS_4_6
    )

    # AWS credentials are loaded from:
    # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    # 2. AWS credentials file (~/.aws/credentials)
    # 3. IAM role (when running on AWS)

    # Optional: AWS profile to use
    profile: Optional[str] = os.getenv("AWS_PROFILE")


@dataclass
class AgentConfig:
    """Agent configuration."""

    # Maximum turns per agent session
    max_turns: int = int(os.getenv("AGENT_MAX_TURNS", "50"))

    # Context threshold for handoff (0.0 - 1.0)
    context_threshold: float = float(os.getenv("CONTEXT_THRESHOLD", "0.75"))

    # Maximum context tokens
    max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "200000"))

    # Maximum validation attempts per feature (initial implementation + fix rounds)
    max_validation_attempts: int = int(os.getenv("MAX_VALIDATION_ATTEMPTS", "3"))


@dataclass
class AnalysisConfig:
    """Configuration for AI-agent-based codebase analysis."""

    # Model for analysis (Opus 4.6 — most capable for deep codebase understanding)
    model_id: str = os.getenv(
        "ANALYSIS_MODEL_ID",
        BedrockModels.OPUS_4_6,
    )

    # Maximum tool-use turns per analysis session
    max_turns: int = int(os.getenv("ANALYSIS_MAX_TURNS", "25"))

    # Whether to use agent-based analysis (set to "false" to force deterministic)
    use_agent: bool = os.getenv("ANALYSIS_USE_AGENT", "true").lower() == "true"

    # Maximum file tree depth for initial context
    max_tree_depth: int = int(os.getenv("ANALYSIS_MAX_TREE_DEPTH", "4"))


@dataclass
class PricingConfig:
    """Model pricing configuration loaded from a JSON file."""

    # Mapping of model_id -> {"input_price_per_1k_tokens": float, "output_price_per_1k_tokens": float}
    models: dict = field(default_factory=dict)
    default: dict = field(default_factory=lambda: {
        "input_price_per_1k_tokens": 0.003,
        "output_price_per_1k_tokens": 0.015,
    })

    _DEFAULT_PRICING = {
        "input_price_per_1k_tokens": 0.003,
        "output_price_per_1k_tokens": 0.015,
    }

    @classmethod
    def load(cls) -> "PricingConfig":
        """Load pricing config from JSON file.

        Looks for PRICING_CONFIG_PATH env var, then pricing.json in project root.
        Falls back to empty config with defaults if file not found.
        """
        config_path = os.getenv("PRICING_CONFIG_PATH")
        if not config_path:
            # Look for pricing.json relative to this file (project root)
            project_root = Path(__file__).parent.parent
            config_path = str(project_root / "pricing.json")

        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            return cls(
                models=data.get("models", {}),
                default=data.get("default", cls._DEFAULT_PRICING),
            )
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load pricing config from {config_path}: {e}")
            print("   Using default pricing.")
            return cls()

    def get_pricing(self, model_id: str) -> dict:
        """Get pricing for a specific model ID.

        Returns:
            Dict with 'input_price_per_1k_tokens' and 'output_price_per_1k_tokens'
        """
        return self.models.get(model_id, self.default)

    def calculate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> tuple[float, float]:
        """Calculate cost for a given model and token counts.

        Returns:
            Tuple of (input_cost, output_cost)
        """
        pricing = self.get_pricing(model_id)
        input_cost = (input_tokens / 1000) * pricing["input_price_per_1k_tokens"]
        output_cost = (output_tokens / 1000) * pricing["output_price_per_1k_tokens"]
        return input_cost, output_cost


# Global config instances
bedrock_config = BedrockConfig()
agent_config = AgentConfig()
analysis_config = AnalysisConfig()
pricing_config = PricingConfig.load()


def get_bedrock_model_id() -> str:
    """Get the Bedrock model ID to use."""
    return bedrock_config.model_id


def get_aws_region() -> str:
    """Get the AWS region for Bedrock."""
    return bedrock_config.region
