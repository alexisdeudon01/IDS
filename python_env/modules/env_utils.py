"""
Environment utility helpers for configuration placeholders.
"""

import os
from typing import Optional


def validate_env_placeholder(value: Optional[str], placeholder: str, env_var: str, label: str) -> None:
    """Validate that an environment variable is set if placeholder is used."""
    if value == placeholder and not os.getenv(env_var):
        raise ValueError(
            f"{label} is set to placeholder but environment variable '{env_var}' is not set."
        )


def resolve_env_placeholder(
    value: Optional[str],
    placeholder: str,
    env_var: str,
    label: str,
    required: bool = True,
) -> Optional[str]:
    """
    Resolve placeholder values to environment variables.

    Args:
        value: Current configuration value.
        placeholder: Placeholder string to match.
        env_var: Environment variable to use when placeholder matches.
        label: Human-readable label for error messaging.
        required: Whether env var must be set when placeholder matches.

    Returns:
        Resolved value (env var) or original value.
    """
    if value == placeholder:
        resolved = os.getenv(env_var)
        if required and not resolved:
            raise ValueError(
                f"{label} is set to placeholder but environment variable '{env_var}' is not set."
            )
        return resolved
    return value
