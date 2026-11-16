#!/usr/bin/env bash
# Create or update Modal secrets without passing the values as process arguments.
# Terraform provides MODAL_TOKEN_ID, MODAL_TOKEN_SECRET, MODAL_ENVIRONMENT,
# DEPLOY_PATH, and SECRETS_JSON in the environment.

set -euo pipefail

uv run --directory "${DEPLOY_PATH:?DEPLOY_PATH is required}" python - <<'PYTHON'
import json
import os
import re

from modal import Secret


def valid_secret(entry):
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and re.fullmatch(r"[a-zA-Z0-9_-]+", entry["name"])
        and isinstance(entry.get("values"), dict)
        and bool(entry["values"])
        and all(
            re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", key)
            and isinstance(value, str)
            for key, value in entry["values"].items()
        )
    )


environment = os.environ.get("MODAL_ENVIRONMENT")
if not environment:
    raise SystemExit("MODAL_ENVIRONMENT is required")

try:
    secrets = json.loads(os.environ.pop("SECRETS_JSON", ""))
except json.JSONDecodeError:
    raise SystemExit("Invalid SECRETS_JSON") from None

if not isinstance(secrets, list) or not all(valid_secret(entry) for entry in secrets):
    raise SystemExit("Invalid Modal secret name or value map")

for entry in secrets:
    name = entry["name"]
    try:
        # Modal 1.6.3's CLI uses this SDK call for atomic --force replacement.
        Secret._create_deployed(name, entry["values"], environment_name=environment, overwrite=True)
    except Exception as exc:
        raise SystemExit(f"Failed to provision Modal secret {name}: {type(exc).__name__}") from None
    print(f"Provisioned Modal secret {name}")
PYTHON
