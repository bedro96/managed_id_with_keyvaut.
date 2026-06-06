from __future__ import annotations

from pathlib import Path

from pytest import CaptureFixture, MonkeyPatch

from utility import keyvault_env


def test_parse_env_text_handles_comments_quotes_and_export() -> None:
    content = """
    # comment
    FOO=bar
    EMPTY=
    export QUOTED="hello world"
    SINGLE='value=with=equals'
    """

    assert keyvault_env.parse_env_text(content) == {
        "EMPTY": "",
        "FOO": "bar",
        "QUOTED": "hello world",
        "SINGLE": "value=with=equals",
    }


def test_write_load_and_preview_env_file(tmp_path: Path) -> None:
    env_path = keyvault_env.write_env_file("FOO=secret\nSMALL=abc\nEMPTY=\n", tmp_path / ".env")

    loaded = keyvault_env.load_env_file(env_path)
    preview = keyvault_env.format_env_preview(env_path)

    assert loaded == {"EMPTY": "", "FOO": "secret", "SMALL": "abc"}
    assert "EMPTY=<empty>" in preview
    assert "FOO=se***et" in preview
    assert "SMALL=****" in preview


def test_render_test_page_escapes_values(tmp_path: Path) -> None:
    env_path = keyvault_env.write_env_file("TOKEN=<script>alert(1)</script>\n", tmp_path / ".env")

    page = keyvault_env.render_test_page(env_path, show_values=True)

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script>alert(1)</script>" not in page


def test_retrieve_env_from_keyvault_uses_dev_auth_and_loads(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    class Secret:
        value = "FOO=bar\n"

    class Client:
        def get_secret(self, name: str) -> Secret:
            assert name == "app-env"
            return Secret()

    monkeypatch.setattr(keyvault_env, "_secret_client", lambda vault_url, use_managed_identity: Client())
    env_path = tmp_path / ".env"

    result = keyvault_env.retrieve_env_from_keyvault(
        "https://example.vault.azure.net/",
        output_file=env_path,
        use_managed_identity=False,
    )

    assert result.path == env_path.resolve()
    assert result.keys == ("FOO",)


def test_upload_env_to_keyvault_sets_secret(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []

    class Client:
        def set_secret(self, name: str, value: str, content_type: str) -> None:
            calls.append((name, value, content_type))

    monkeypatch.setattr(keyvault_env, "_secret_client", lambda vault_url, use_managed_identity: Client())
    env_path = keyvault_env.write_env_file("FOO=bar\n", tmp_path / ".env")

    result = keyvault_env.upload_env_to_keyvault(
        "https://example.vault.azure.net/",
        env_file=env_path,
        use_managed_identity=False,
    )

    assert result.keys == ("FOO",)
    assert calls == [("app-env", "FOO=bar\n", "text/plain")]


def test_main_without_command_bootstraps_and_prints(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    monkeypatch.setenv("KEY_VAULT_URL", "https://example.vault.azure.net/")

    def bootstrap_env_from_keyvault(*, use_managed_identity: bool = True) -> keyvault_env.EnvFileResult:
        assert use_managed_identity is True
        return keyvault_env.EnvFileResult(path=Path(".env").resolve(), keys=("FOO",))

    monkeypatch.setattr(keyvault_env, "bootstrap_env_from_keyvault", bootstrap_env_from_keyvault)
    monkeypatch.setattr(keyvault_env, "format_env_preview", lambda path: "FOO=****")

    keyvault_env.main([])

    captured = capsys.readouterr()
    assert "Retrieved 1 values into" in captured.out
    assert "FOO=****" in captured.out
