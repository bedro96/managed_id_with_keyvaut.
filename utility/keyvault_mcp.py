from __future__ import annotations

import os
from pathlib import Path

from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from fastmcp import FastMCP


def dump_env_from_keyvault(vault_url: str, env_secret_name: str, output_file: str = ".env") -> Path:
    """Fetch a Key Vault secret and write it as .env file content."""
    credential = ManagedIdentityCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    try:
        secret_value = client.get_secret(env_secret_name).value or ""
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read secret '{env_secret_name}' from Key Vault '{vault_url}'"
        ) from exc

    env_path = Path(output_file)
    base_env_path = (Path.cwd().resolve() / ".env").resolve()
    resolved_env_path = (Path.cwd().resolve() / env_path).resolve()
    if env_path.is_absolute() or env_path.name != ".env" or resolved_env_path != base_env_path:
        raise ValueError("output_file must be '.env' in the current working directory")

    fd = os.open(resolved_env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        env_file = os.fdopen(fd, "w", encoding="utf-8")
    except Exception:
        os.close(fd)
        raise

    with env_file:
        env_file.write(secret_value)

    return resolved_env_path


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader for KEY=VALUE lines."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
            continue
        key, value = cleaned.split("=", 1)
        normalized_value = value.strip()
        if len(normalized_value) >= 2 and normalized_value[0] == normalized_value[-1] and normalized_value[0] in {"'", '"'}:
            normalized_value = normalized_value[1:-1]
        os.environ[key.strip()] = normalized_value


def parse_allowed_keys(value: str) -> set[str]:
    return {key.strip() for key in value.split(",") if key.strip()}


def create_mcp_server(allowed_config_keys: set[str], app_name: str = "managed-identity-keyvault-sample") -> FastMCP:
    mcp = FastMCP(app_name)

    @mcp.tool()
    def get_config_value(key: str) -> str:
        """Return an allowed value from environment loaded from Key Vault .env secret."""
        if key not in allowed_config_keys:
            raise PermissionError(f"Access denied for key '{key}'")
        value = os.getenv(key)
        if value is None:
            raise KeyError(f"Configured key '{key}' is not set in environment")
        return value

    return mcp


def run_main() -> None:
    vault_url = os.environ.get("KEY_VAULT_URL")
    if not vault_url:
        raise RuntimeError("KEY_VAULT_URL environment variable is required")

    env_secret_name = os.environ.get("KEY_VAULT_ENV_SECRET_NAME", "app-env")
    dump_env_from_keyvault(vault_url=vault_url, env_secret_name=env_secret_name)
    load_dotenv(".env")

    allowed_keys = parse_allowed_keys(os.environ.get("MCP_ALLOWED_KEYS", ""))
    if not allowed_keys:
        raise RuntimeError("MCP_ALLOWED_KEYS must contain at least one allowed key")
    mcp = create_mcp_server(allowed_config_keys=allowed_keys)
    mcp.run()
