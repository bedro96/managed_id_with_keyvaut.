# managed_id_with_keyvaut.
managed_id_with_keyvaut

## sample.example (FastMCP + Key Vault + system managed identity)

`sample.example` shows how to:
- authenticate to Azure Key Vault with **ManagedIdentityCredential**
- get one secret that contains `.env` file content
- dump it to a local `.env` file
- load those values and expose them via a FastMCP tool (`get_config_value`)

### Required environment variables
- `KEY_VAULT_URL` (example: `https://<vault-name>.vault.azure.net/`)
- `KEY_VAULT_ENV_SECRET_NAME` (optional, default: `app-env`)
- `MCP_ALLOWED_KEYS` (comma-separated keys that `get_config_value` can return)

### Run
```bash
pip install fastmcp azure-identity azure-keyvault-secrets
python sample.example
```
