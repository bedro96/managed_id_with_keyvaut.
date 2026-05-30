# managed_id_with_keyvault.

Reusable Python utilities that use an Azure **Managed Identity** to read and write a complete `.env` file as a single Azure Key Vault secret, plus a small FastMCP sample server that exposes selected values via a tool.

## Module layout
- `utility/keyvault_mcp.py` — FastMCP server helpers (`dump_env_from_keyvault`, `load_dotenv`, `parse_allowed_keys`, `create_mcp_server`, `run_main`).
- `utility/read_env_from_keyvault.py` — generic, importable utility that fetches a Key Vault secret and writes its value to a `.env` file.
- `utility/save_env_to_keyvault.py` — generic, importable utility that uploads the contents of a `.env` file as a single Key Vault secret.
- `main.py` — entrypoint that delegates to `utility/keyvault_mcp.py::run_main`.
- `sample.example` — compatibility wrapper that also runs the same module.

## Install / sync dependencies

Dependencies are declared in `pyproject.toml`. Use either pip or uv:

```bash
# pip (editable install pulls in fastmcp, azure-identity, azure-keyvault-secrets)
pip install -e .

# or uv
uv sync
```

## Required environment variables (for the FastMCP sample)
- `KEY_VAULT_URL` — e.g. `https://<vault-name>.vault.azure.net/`
- `KEY_VAULT_ENV_SECRET_NAME` — optional, default `app-env`
- `MCP_ALLOWED_KEYS` — comma-separated list of keys that `get_config_value` is permitted to return

## Run the FastMCP server
```bash
python main.py
```

`sample.example` is kept as a compatibility wrapper and runs the same module.

## How to use the functions

All utilities authenticate via `azure.identity.ManagedIdentityCredential`, so they must run in an environment where a system- or user-assigned managed identity is available and has at least `get`/`set` permissions on the target Key Vault secret.

### `read_env_from_keyvault(vault_url, env_secret_name, output_file=".env") -> pathlib.Path`

Fetch a single Key Vault secret and write its value to a local `.env` file. The output file is created with mode `0o600`.

| Parameter | Description |
| --- | --- |
| `vault_url` | Full Key Vault URL, e.g. `https://<vault>.vault.azure.net/`. |
| `env_secret_name` | Name of the secret whose value is the full `.env` content. |
| `output_file` | Path to write (default `.env` in CWD). Parent dirs are created. |

Returns the resolved `Path` of the file that was written. Raises `RuntimeError` if the secret cannot be read.

```python
from utility.read_env_from_keyvault import read_env_from_keyvault

written = read_env_from_keyvault(
    vault_url="https://my-vault.vault.azure.net/",
    env_secret_name="app-env",
    output_file=".env",
)
print(f"Wrote {written}")
```

### `save_env_to_keyvault(vault_url, env_secret_name, input_file=".env") -> str`

Read a local `.env` file and store its full contents as the value of a single Key Vault secret.

| Parameter | Description |
| --- | --- |
| `vault_url` | Full Key Vault URL. |
| `env_secret_name` | Name of the secret to create or update. |
| `input_file` | Path of the `.env` file to upload (default `.env` in CWD). |

Returns the secret version id (URL) returned by Key Vault. Raises `FileNotFoundError` if `input_file` is missing, or `RuntimeError` on Key Vault failure.

```python
from utility.save_env_to_keyvault import save_env_to_keyvault

secret_id = save_env_to_keyvault(
    vault_url="https://my-vault.vault.azure.net/",
    env_secret_name="app-env",
    input_file=".env",
)
print(secret_id)
```

### `utility.keyvault_mcp` helpers

- `dump_env_from_keyvault(vault_url, env_secret_name, output_file=".env") -> Path` — same as `read_env_from_keyvault` but constrained to write `.env` in the current working directory; used by the FastMCP entrypoint.
- `load_dotenv(path=".env") -> None` — minimal `KEY=VALUE` loader that populates `os.environ`. Strips surrounding matched quotes and ignores blanks/comments.
- `parse_allowed_keys(value: str) -> set[str]` — parse a comma-separated allow-list into a set.
- `create_mcp_server(allowed_config_keys, app_name="managed-identity-keyvault-sample") -> FastMCP` — build a `FastMCP` server exposing a `get_config_value(key)` tool that returns env values only for keys in `allowed_config_keys`.
- `run_main() -> None` — full sample wiring: read `KEY_VAULT_URL` / `KEY_VAULT_ENV_SECRET_NAME` / `MCP_ALLOWED_KEYS`, dump the secret, load it, then start the FastMCP server.

```python
from utility.keyvault_mcp import (
    dump_env_from_keyvault,
    load_dotenv,
    parse_allowed_keys,
    create_mcp_server,
)

dump_env_from_keyvault("https://my-vault.vault.azure.net/", "app-env")
load_dotenv(".env")
allowed = parse_allowed_keys("DB_HOST,DB_USER")
mcp = create_mcp_server(allowed_config_keys=allowed)
mcp.run()
```
