"""Validation for settings that must not have committed default secrets."""
import os


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(
            f"{name} must be configured in backend/.env or the environment. "
            "See backend/.env.example and docs/SETUP.md."
        )
    return value
