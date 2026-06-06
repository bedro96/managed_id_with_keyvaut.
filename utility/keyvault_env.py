from __future__ import annotations

import argparse
import html
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_SECRET_NAME = "app-env"
EXPORT_PREFIX = "export "
MASK_THRESHOLD = 6
MASK_PREFIX_SUFFIX_LEN = 2


@dataclass(frozen=True)
class EnvFileResult:
    """Summary of a local .env file operation."""

    path: Path
    keys: tuple[str, ...]


@dataclass(frozen=True)
class EnvValuePreview:
    """Display-safe representation of a .env value."""

    key: str
    value: str


def _credential(use_managed_identity: bool) -> Any:
    if use_managed_identity:
        from azure.identity import ManagedIdentityCredential

        return ManagedIdentityCredential()

    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(exclude_managed_identity_credential=True)


def _secret_client(vault_url: str, use_managed_identity: bool) -> Any:
    from azure.keyvault.secrets import SecretClient

    return SecretClient(vault_url=vault_url, credential=_credential(use_managed_identity))


def parse_env_text(content: str) -> dict[str, str]:
    """Parse KEY=VALUE lines from .env content."""
    values: dict[str, str] = {}
    for line_number, line in enumerate(content.splitlines(), start=1):
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        if cleaned.startswith(EXPORT_PREFIX):
            cleaned = cleaned.removeprefix(EXPORT_PREFIX).lstrip()
        if "=" not in cleaned:
            continue
        key, value = cleaned.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Malformed .env line {line_number} contains an empty key")
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {"'", '"'}
        ):
            normalized_value = normalized_value[1:-1]
        values[key] = normalized_value
    return values


def load_env_file(path: str | Path = ".env", *, override: bool = True) -> dict[str, str]:
    """Load KEY=VALUE pairs from a .env file into os.environ."""
    env_path = Path(path)
    values = parse_env_text(env_path.read_text(encoding="utf-8"))
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return values


def write_env_file(content: str, output_file: str | Path = ".env") -> Path:
    """Write .env content to disk using owner-only permissions where supported."""
    env_path = Path(output_file)
    if env_path.exists() and env_path.is_dir():
        raise ValueError(f"output_file points to a directory: {env_path}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        env_file = os.fdopen(fd, "w", encoding="utf-8")
    except Exception:
        os.close(fd)
        raise
    with env_file:
        env_file.write(content)
    return env_path.resolve()


def retrieve_env_from_keyvault(
    vault_url: str,
    env_secret_name: str = DEFAULT_SECRET_NAME,
    *,
    output_file: str | Path = ".env",
    use_managed_identity: bool = True,
    load_into_os_environ: bool = True,
) -> EnvFileResult:
    """Retrieve .env content, write it locally, and optionally load os.environ."""
    client = _secret_client(vault_url, use_managed_identity)
    try:
        secret_value = client.get_secret(env_secret_name).value or ""
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read secret '{env_secret_name}' from Key Vault '{vault_url}'"
        ) from exc

    env_path = write_env_file(secret_value, output_file)
    values = load_env_file(env_path) if load_into_os_environ else parse_env_text(secret_value)
    return EnvFileResult(path=env_path, keys=tuple(sorted(values)))


def upload_env_to_keyvault(
    vault_url: str,
    env_secret_name: str = DEFAULT_SECRET_NAME,
    *,
    env_file: str | Path = ".env",
    use_managed_identity: bool = True,
) -> EnvFileResult:
    """Upload local .env file content to a Key Vault secret."""
    env_path = Path(env_file)
    content = env_path.read_text(encoding="utf-8")
    values = parse_env_text(content)
    client = _secret_client(vault_url, use_managed_identity)
    try:
        client.set_secret(env_secret_name, content, content_type="text/plain")
    except Exception as exc:
        raise RuntimeError(
            f"Failed to write secret '{env_secret_name}' to Key Vault '{vault_url}'"
        ) from exc
    return EnvFileResult(path=env_path.resolve(), keys=tuple(sorted(values)))


def preview_env_file(
    path: str | Path = ".env",
    *,
    show_values: bool = False,
) -> tuple[EnvValuePreview, ...]:
    """Return display-safe .env key/value previews."""
    values = load_env_file(path, override=False)
    previews: list[EnvValuePreview] = []
    for key in sorted(values):
        value = values[key] if show_values else _mask_value(values[key])
        previews.append(EnvValuePreview(key=key, value=value))
    return tuple(previews)


def format_env_preview(path: str | Path = ".env", *, show_values: bool = False) -> str:
    """Format .env previews for CLI or test-page display."""
    previews = preview_env_file(path, show_values=show_values)
    if not previews:
        return "No values found."
    return "\n".join(f"{preview.key}={preview.value}" for preview in previews)


def _mask_value(value: str) -> str:
    if value == "":
        return "<empty>"
    if len(value) <= MASK_THRESHOLD:
        return "****"
    return f"{value[:MASK_PREFIX_SUFFIX_LEN]}***{value[-MASK_PREFIX_SUFFIX_LEN:]}"


def render_test_page(path: str | Path = ".env", *, show_values: bool = False) -> str:
    rows = []
    for preview in preview_env_file(path, show_values=show_values):
        rows.append(
            "<tr>"
            f"<td>{html.escape(preview.key)}</td>"
            f"<td><code>{html.escape(preview.value)}</code></td>"
            "</tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="2">No values found.</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Key Vault .env verification</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; min-width: 24rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; }}
  </style>
</head>
<body>
  <h1>Key Vault .env verification</h1>
  <p>Source: <code>{html.escape(str(path))}</code></p>
  <table>
    <thead><tr><th>Key</th><th>Value</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</body>
</html>"""


def serve_test_page(
    path: str | Path = ".env",
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    show_values: bool = False,
) -> None:
    """Serve a local verification page for the retrieved .env file."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            page = render_test_page(path, show_values=show_values).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, msg_format: str, *args: object) -> None:
            # Suppress HTTP request logs to keep output focused on the server address.
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving verification page at http://{host}:{port}")
    server.serve_forever()


def bootstrap_env_from_keyvault(*, use_managed_identity: bool = True) -> EnvFileResult:
    """Retrieve .env using environment variables and load it into os.environ."""
    vault_url = os.environ.get("KEY_VAULT_URL")
    if not vault_url:
        raise RuntimeError("KEY_VAULT_URL environment variable is required")
    env_secret_name = os.environ.get("KEY_VAULT_ENV_SECRET_NAME", DEFAULT_SECRET_NAME)
    return retrieve_env_from_keyvault(
        vault_url=vault_url,
        env_secret_name=env_secret_name,
        use_managed_identity=use_managed_identity,
    )


def _vault_url_from_args(value: str | None) -> str:
    vault_url = value or os.environ.get("KEY_VAULT_URL")
    if not vault_url:
        raise RuntimeError("Provide --vault-url or set KEY_VAULT_URL")
    return vault_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Azure Key Vault .env bootstrap utility")
    parser.add_argument(
        "--dev-auth",
        dest="bootstrap_dev_auth",
        action="store_true",
        help="Use DefaultAzureCredential for the no-command bootstrap path",
    )
    subcommands = parser.add_subparsers(dest="command")

    download = subcommands.add_parser("download", help="Retrieve .env content from Key Vault")
    download.add_argument("--vault-url")
    download.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    download.add_argument("--output-file", default=".env")
    download.add_argument("--dev-auth", action="store_true", help="Use DefaultAzureCredential")
    download.add_argument("--show-values", action="store_true")
    download.add_argument("--no-load", action="store_true")

    upload = subcommands.add_parser("upload", help="Upload local .env content to Key Vault")
    upload.add_argument("--vault-url")
    upload.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    upload.add_argument("--env-file", default=".env")
    upload.add_argument("--dev-auth", action="store_true", help="Use DefaultAzureCredential")

    verify = subcommands.add_parser("verify", help="Print retrieved .env values")
    verify.add_argument("--env-file", default=".env")
    verify.add_argument("--show-values", action="store_true")

    page = subcommands.add_parser("serve-test-page", help="Serve a local verification page")
    page.add_argument("--env-file", default=".env")
    page.add_argument("--host", default="127.0.0.1")
    page.add_argument("--port", type=int, default=8000)
    page.add_argument("--show-values", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "download":
        result = retrieve_env_from_keyvault(
            vault_url=_vault_url_from_args(args.vault_url),
            env_secret_name=args.secret_name,
            output_file=args.output_file,
            use_managed_identity=not args.dev_auth,
            load_into_os_environ=not args.no_load,
        )
        print(f"Retrieved {len(result.keys)} values into {result.path}")
        print(format_env_preview(result.path, show_values=args.show_values))
    elif args.command == "upload":
        result = upload_env_to_keyvault(
            vault_url=_vault_url_from_args(args.vault_url),
            env_secret_name=args.secret_name,
            env_file=args.env_file,
            use_managed_identity=not args.dev_auth,
        )
        print(f"Uploaded {len(result.keys)} values from {result.path}")
    elif args.command == "verify":
        print(format_env_preview(args.env_file, show_values=args.show_values))
    elif args.command == "serve-test-page":
        serve_test_page(
            args.env_file,
            host=args.host,
            port=args.port,
            show_values=args.show_values,
        )
    else:
        result = bootstrap_env_from_keyvault(use_managed_identity=not args.bootstrap_dev_auth)
        print(f"Retrieved {len(result.keys)} values into {result.path}")
        print(format_env_preview(result.path))


if __name__ == "__main__":
    main()
