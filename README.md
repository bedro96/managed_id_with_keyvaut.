# managed_id_with_keyvault.
managed_id_with_keyvault

## FastMCP + Key Vault + system managed identity

`sample.example` shows how to:
- authenticate to Azure Key Vault with **ManagedIdentityCredential**
- get one secret that contains `.env` file content
- dump it to a local `.env` file
- load those values and expose them via a FastMCP tool (`get_config_value`)

### Reusable module layout
- `utility/keyvault_mcp.py` contains reusable logic (Key Vault fetch, dotenv load, MCP server creation)
- `utility/read_env_from_keyvault.py` generic, importable utility that uses Managed Identity to fetch a Key Vault secret and dump it as a `.env` file
- `utility/save_env_to_keyvault.py` generic, importable utility that uses Managed Identity to save a complete `.env` file as a single Key Vault secret
- `main.py` is the main entrypoint that calls the utility module
- `sample.example` is a compatibility wrapper that also calls the same utility module

#### Generic utility usage
```python
from utility.read_env_from_keyvault import read_env_from_keyvault
from utility.save_env_to_keyvault import save_env_to_keyvault

read_env_from_keyvault(vault_url="https://<vault>.vault.azure.net/", env_secret_name="app-env", output_file=".env")
save_env_to_keyvault(vault_url="https://<vault>.vault.azure.net/", env_secret_name="app-env", input_file=".env")
```

### Required environment variables
- `KEY_VAULT_URL` (example: `https://<vault-name>.vault.azure.net/`)
- `KEY_VAULT_ENV_SECRET_NAME` (optional, default: `app-env`)
- `MCP_ALLOWED_KEYS` (comma-separated keys that `get_config_value` can return)

### Run
```bash
pip install fastmcp azure-identity azure-keyvault-secrets
python main.py
```

`sample.example` is kept as a compatibility wrapper and also runs the same module.
