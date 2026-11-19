import pytest

from packages.analyzers.code.repo_url import GitImportError, check_repo_url, split_ref


@pytest.mark.parametrize(
    "url",
    ["https://github.com/acme/shop.git", "https://gitlab.internal.example/x.git#main",
     "https://10.0.0.5/team/repo.git", "https://[2001:db8::1]/r.git"],
)  # fmt: skip
def test_allowed(url: str) -> None:
    assert check_repo_url(url) == url.split("#")[0]


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://github.com/a/b", "Only https"),
        ("ssh://git@github.com/a/b", "Only https"),
        ("file:///etc", "Only https"),
        ("https://user:pw@github.com/a/b", "plain URL"),
        ("https:///nohost", "plain URL"),
        ("https://localhost/r", "not allowed"),
        ("https://app.localhost/r", "not allowed"),
        ("https://metadata.google.internal/x", "not allowed"),
        ("https://127.0.0.1/r", "not allowed"),
        ("https://169.254.169.254/latest", "not allowed"),
        ("https://[::1]/r", "not allowed"),
        ("https://0.0.0.0/r", "not allowed"),
        ("https://224.0.0.1/r", "not allowed"),
    ],
)
def test_blocked(url: str, message: str) -> None:
    with pytest.raises(GitImportError, match=message):
        check_repo_url(url)


def test_file_only_when_allowed_and_split_ref() -> None:
    assert check_repo_url("file:///tmp/r#dev", ("file",)) == "file:///tmp/r"
    assert split_ref("https://h/r.git#release/1.2") == ("https://h/r.git", "release/1.2")
    assert split_ref("https://h/r.git") == ("https://h/r.git", None)
