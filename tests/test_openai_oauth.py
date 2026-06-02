from __future__ import annotations

from io import BytesIO

from planner.openai_oauth import (
    DEFAULT_OPENAI_OAUTH_MODELS,
    DEFAULT_OPENAI_OAUTH_BASE_URL,
    OpenAIOAuthProcess,
    build_codex_login_command,
    build_proxy_command,
    candidate_auth_files,
    check_openai_oauth_proxy,
    find_existing_auth_file,
    start_codex_login,
    start_openai_oauth_proxy,
)


class FakeProcess:
    pid = 12345


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return BytesIO(self.payload)

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_candidate_auth_files_prefers_explicit_env(tmp_path):
    explicit = tmp_path / "explicit-auth.json"
    chatgpt_home = tmp_path / "chatgpt"

    files = candidate_auth_files(
        env={
            "OPENAI_OAUTH_FILE": str(explicit),
            "CHATGPT_LOCAL_HOME": str(chatgpt_home),
        },
        home=tmp_path / "home",
    )

    assert files[0] == explicit
    assert chatgpt_home / "auth.json" in files
    assert tmp_path / "home" / ".codex" / "auth.json" in files


def test_find_existing_auth_file_returns_first_match(tmp_path):
    missing = tmp_path / "missing.json"
    existing = tmp_path / "auth.json"
    existing.write_text("{}", encoding="utf-8")

    assert find_existing_auth_file([missing, existing]) == existing


def test_build_commands_match_package_scripts():
    assert build_codex_login_command() == ["npx", "@openai/codex", "login"]
    assert build_proxy_command() == [
        "npm",
        "run",
        "llm:proxy",
        "--",
        "--models",
        ",".join(DEFAULT_OPENAI_OAUTH_MODELS),
    ]
    assert build_proxy_command(env={"OPENAI_OAUTH_MODELS": "gpt-5.4"}) == [
        "npm",
        "run",
        "llm:proxy",
        "--",
        "--models",
        "gpt-5.4",
    ]


def test_start_process_helpers_return_pid_and_command(tmp_path):
    calls = []

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return FakeProcess()

    login = start_codex_login(popen=fake_popen, cwd=tmp_path)
    proxy = start_openai_oauth_proxy(popen=fake_popen, cwd=tmp_path)

    assert login == OpenAIOAuthProcess(pid=12345, command=["npx", "@openai/codex", "login"])
    assert proxy.command[:4] == ["npm", "run", "llm:proxy", "--"]
    assert proxy.pid == 12345
    assert calls[0][1]["cwd"] == tmp_path


def test_check_openai_oauth_proxy_parses_models_response():
    def fake_urlopen(request, timeout):
        assert request.full_url == f"{DEFAULT_OPENAI_OAUTH_BASE_URL}/models"
        assert timeout == 2.0
        return FakeResponse(b'{"data":[{"id":"gpt-5"},{"id":"gpt-4.1"}]}')

    status = check_openai_oauth_proxy(urlopen=fake_urlopen)

    assert status.connected is True
    assert status.models == ["gpt-5", "gpt-4.1"]
