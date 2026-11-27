import json
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apps.cli import main as cli
from apps.runner.secrets import EnvSecrets, Resolver
from apps.runner.vault import Vault, VaultError, new_key


@pytest.mark.parametrize("key", [new_key(), "a long passphrase here", "abcdabcdabcdabcd"])
def test_roundtrip_encrypted_at_rest(tmp_path: Path, key: str) -> None:
    path = tmp_path / "v" / "vault.json"
    v = Vault(path, key)
    assert v.names() == [] and v.get("admin_password") is None
    v.set("admin_password", "S3cret-admin!")
    v.set("teacher_password", "t-pass-123")
    assert "S3cret-admin" not in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    again = Vault(path, key)
    assert again.names() == ["admin_password", "teacher_password"]
    assert again.get("admin_password") == "S3cret-admin!"
    r = Resolver(EnvSecrets({}), again)
    assert r.resolve("{{secret:teacher_password}}") == "t-pass-123"
    assert again.remove("teacher_password") and not again.remove("teacher_password")
    assert Vault(path, key).names() == ["admin_password"]


def test_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "vault.json"
    Vault(path, new_key()).set("a", "b")
    with pytest.raises(VaultError, match="Wrong vault key"):
        Vault(path, new_key()).names()
    blob = json.loads(path.read_text())
    blob["data"] = blob["data"][:-4] + "AAAA"
    path.write_text(json.dumps(blob))
    with pytest.raises(VaultError):
        Vault(path, "whatever passphrase").names()
    path.write_text("{not json")
    with pytest.raises(VaultError, match="corrupt"):
        Vault(path, new_key()).names()
    path.write_text(json.dumps({**blob, "v": 9}))
    with pytest.raises(VaultError, match="version"):
        Vault(path, new_key()).names()
    with pytest.raises(VaultError, match="passphrase"):
        Vault(tmp_path / "x.json", "short").set("a", "b")
    with pytest.raises(VaultError, match="Names"):
        Vault(tmp_path / "x.json", new_key()).set("Bad Name", "b")


def test_failed_write_leaves_no_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    v = Vault(tmp_path / "vault.json", new_key())

    def boom(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("apps.runner.vault.os.replace", boom)
    with pytest.raises(OSError):
        v.set("a", "b")
    assert list(tmp_path.iterdir()) == []


def test_from_env(tmp_path: Path) -> None:
    assert Vault.from_env({}) is None
    with pytest.raises(VaultError, match="KEY"):
        Vault.from_env({"SAQ_VAULT_FILE": str(tmp_path / "v.json")})
    v = Vault.from_env({"SAQ_VAULT_FILE": str(tmp_path / "v.json"), "SAQ_VAULT_KEY": new_key()})
    assert v is not None and v.path.name == "v.json"
    assert isinstance(Vault.from_env(), Vault | None)


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = CliRunner()
    monkeypatch.delenv("SAQ_VAULT_FILE", raising=False)
    assert "Set SAQ_VAULT_FILE" in run.invoke(cli.app, ["vault", "list"]).output
    monkeypatch.setenv("SAQ_VAULT_FILE", str(tmp_path / "v.json"))
    monkeypatch.delenv("SAQ_VAULT_KEY", raising=False)
    assert "SAQ_VAULT_KEY is missing" in run.invoke(cli.app, ["vault", "list"]).output
    key = run.invoke(cli.app, ["vault", "keygen"]).output.strip()
    monkeypatch.setenv("SAQ_VAULT_KEY", key)
    out = run.invoke(cli.app, ["vault", "set", "admin_password"], input="pw-123\npw-123\n")
    assert (
        out.exit_code == 0 and "stored admin_password" in out.output and "pw-123" not in out.output
    )
    assert run.invoke(cli.app, ["vault", "list"]).output.strip() == "admin_password"
    bad = run.invoke(cli.app, ["vault", "set", "Bad Name", "--value", "x"])
    assert bad.exit_code == 1 and "Names" in bad.output
    assert run.invoke(cli.app, ["vault", "rm", "admin_password"]).exit_code == 0
    gone = run.invoke(cli.app, ["vault", "rm", "admin_password"])
    assert gone.exit_code == 1 and "NOT_FOUND" in gone.output
