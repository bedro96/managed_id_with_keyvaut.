# managed_id_with_keyvault

Python helpers to retrieve an application `.env` file from Azure Key Vault as soon as
your Python process starts, then load the values into `os.environ` for the rest of
your application.

The project also includes an upload helper for storing a prepared `.env` file in
Key Vault and verification commands to inspect what was retrieved.

## Requirements

- Python 3.10+
- `azure-identity`
- `azure-keyvault-secrets`

Install with pip:

```bash
python -m pip install azure-identity azure-keyvault-secrets
```

Or with uv:

```bash
uv venv
uv pip install azure-identity azure-keyvault-secrets
```

For development checks:

```bash
uv pip install -e ".[dev]"
ruff check .
mypy .
pytest
```

## Prepare a `.env` file for Key Vault

Create a normal `.env` file that contains one setting per line:

```dotenv
DATABASE_URL=postgresql://example
API_KEY=replace-me
FEATURE_FLAG=true
```

Upload the whole file content into one Key Vault secret:

```bash
python main.py upload \
  --vault-url "https://<vault-name>.vault.azure.net/" \
  --secret-name app-env \
  --env-file .env
```

During local development, when Managed Identity is not available, add `--dev-auth`
to use `DefaultAzureCredential` without Managed Identity:

```bash
python main.py upload \
  --vault-url "https://<vault-name>.vault.azure.net/" \
  --secret-name app-env \
  --env-file .env \
  --dev-auth
```

## Retrieve `.env` early in your application

Set the Key Vault location before your app starts:

```bash
export KEY_VAULT_URL="https://<vault-name>.vault.azure.net/"
export KEY_VAULT_ENV_SECRET_NAME="app-env"
```

Import and call the bootstrap function at the top of your entrypoint, before other
application modules read environment variables:

```python
from utility.keyvault_env import bootstrap_env_from_keyvault

bootstrap_env_from_keyvault()
```

Or call the lower-level function directly:

```python
from utility.keyvault_env import retrieve_env_from_keyvault

retrieve_env_from_keyvault(
    vault_url="https://<vault-name>.vault.azure.net/",
    env_secret_name="app-env",
    output_file=".env",
)
```

The retrieved file is written locally and loaded into `os.environ`.

## Retrieve without Managed Identity for development

Use `--dev-auth` to test with local Azure developer credentials instead of Managed
Identity:

```bash
python main.py download \
  --vault-url "https://<vault-name>.vault.azure.net/" \
  --secret-name app-env \
  --dev-auth
```

## Verify retrieved values

The CLI masks values by default:

```bash
python main.py verify --env-file .env
```

To display actual values during a controlled local test:

```bash
python main.py verify --env-file .env --show-values
```

## Test page for verification

Serve a local verification page for the retrieved `.env` file:

```bash
python main.py serve-test-page --env-file .env
```

Open `http://127.0.0.1:8000` to review the keys and masked values. Add
`--show-values` only in a secure local development environment if you need to see
the full values.
