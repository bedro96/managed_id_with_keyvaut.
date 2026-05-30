"""Generic utility to save a .env file to Key Vault as a single secret.

Uses a system/user assigned Managed Identity to authenticate to Azure Key
Vault and stores the complete contents of a `.env` file as the value of
a single secret.

Can be imported by other code or run directly from the command line.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient


def save_env_to_keyvault(
    vault_url: str,
    env_secret_name: str,
    input_file: str = ".env",
) -> str:
    """Upload the contents of a .env file to Key Vault as one secret.

    Parameters
    ----------
    vault_url:
        Full Key Vault URL, e.g. ``https://<vault-name>.vault.azure.net/``.
    env_secret_name:
        Name of the secret in Key Vault to create or update.
    input_file:
        Path of the .env file whose full contents will be stored as the
        secret value. Defaults to ``.env`` in the current working directory.

    Returns
    -------
    str
        The id (version URL) of the stored secret.
    """
    env_path = Path(input_file).expanduser().resolve()
    if not env_path.is_file():
        raise FileNotFoundError(f"Env file not found: {env_path}")

    secret_value = env_path.read_text(encoding="utf-8")

    credential = ManagedIdentityCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    try:
        stored = client.set_secret(env_secret_name, secret_value)
    except Exception as exc:  # pragma: no cover - network/auth errors
        raise RuntimeError(
            f"Failed to write secret '{env_secret_name}' to Key Vault '{vault_url}'"
        ) from exc

    return stored.id or ""


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Save a .env file to Key Vault as a single secret using "
            "Managed Identity."
        )
    )
    parser.add_argument(
        "--vault-url",
        default=os.environ.get("KEY_VAULT_URL"),
        help="Key Vault URL (default: $KEY_VAULT_URL).",
    )
    parser.add_argument(
        "--secret-name",
        default=os.environ.get("KEY_VAULT_ENV_SECRET_NAME", "app-env"),
        help="Secret name to store the .env contents under "
             "(default: $KEY_VAULT_ENV_SECRET_NAME or 'app-env').",
    )
    parser.add_argument(
        "--input-file",
        default=".env",
        help="Path of the .env file to upload (default: .env).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if not args.vault_url:
        print("error: --vault-url or KEY_VAULT_URL is required", file=sys.stderr)
        return 2

    save_env_to_keyvault(
        vault_url=args.vault_url,
        env_secret_name=args.secret_name,
        input_file=args.input_file,
    )
    print(f"Stored '{args.input_file}' as a Key Vault secret")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
