"""Generic utility to read a Key Vault secret and dump it as a .env file.

Uses a system/user assigned Managed Identity to authenticate to Azure Key
Vault, fetches a single secret whose value is expected to contain the
complete contents of a `.env` file, and writes that value to the given
output path.

Intended to be imported and reused by other code.
"""

from __future__ import annotations

import os
from pathlib import Path

from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient


def read_env_from_keyvault(
    vault_url: str,
    env_secret_name: str,
    output_file: str = ".env",
) -> Path:
    """Fetch a Key Vault secret and write its value as a .env file.

    Parameters
    ----------
    vault_url:
        Full Key Vault URL, e.g. ``https://<vault-name>.vault.azure.net/``.
    env_secret_name:
        Name of the secret in Key Vault whose value is the .env content.
    output_file:
        Path of the .env file to write. Defaults to ``.env`` in the
        current working directory.

    Returns
    -------
    Path
        Resolved path of the file that was written.
    """
    credential = ManagedIdentityCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    try:
        secret_value = client.get_secret(env_secret_name).value or ""
    except Exception as exc:  # pragma: no cover - network/auth errors
        raise RuntimeError(
            f"Failed to read secret '{env_secret_name}' from Key Vault '{vault_url}'"
        ) from exc

    resolved_env_path = Path(output_file).expanduser().resolve()
    resolved_env_path.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(resolved_env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        env_file = os.fdopen(fd, "w", encoding="utf-8")
    except Exception:
        os.close(fd)
        raise

    with env_file:
        env_file.write(secret_value)

    return resolved_env_path
