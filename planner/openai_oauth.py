from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib import request


DEFAULT_OPENAI_OAUTH_BASE_URL = "http://127.0.0.1:10531/v1"
DEFAULT_OPENAI_OAUTH_MODELS = [
    "gpt-5.4",
    "gpt-5.3-codex",
    "gpt-5.3-codex-spark",
    "gpt-5.1",
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
]


@dataclass(frozen=True)
class OpenAIOAuthProcess:
    pid: int
    command: list[str]


@dataclass(frozen=True)
class OpenAIOAuthStatus:
    connected: bool
    message: str
    models: list[str] = field(default_factory=list)


def _dedupe(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    output: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        output.append(path)
    return output


def candidate_auth_files(
    *,
    env: dict[str, str] | None = None,
    home: str | Path | None = None,
) -> list[Path]:
    values = env if env is not None else os.environ
    home_path = Path(home) if home is not None else Path.home()

    candidates: list[Path] = []
    if values.get("OPENAI_OAUTH_FILE"):
        candidates.append(Path(values["OPENAI_OAUTH_FILE"]))
    if values.get("CHATGPT_LOCAL_HOME"):
        candidates.append(Path(values["CHATGPT_LOCAL_HOME"]) / "auth.json")
    if values.get("CODEX_HOME"):
        candidates.append(Path(values["CODEX_HOME"]) / "auth.json")
    if values.get("OPENAI_OAUTH_STORAGE_DIR"):
        candidates.append(Path(values["OPENAI_OAUTH_STORAGE_DIR"]) / "auth.json")

    candidates.extend(
        [
            home_path / ".chatgpt-local" / "auth.json",
            home_path / ".codex" / "auth.json",
        ]
    )
    return _dedupe(candidates)


def find_existing_auth_file(paths: Iterable[str | Path] | None = None) -> Path | None:
    candidates = [Path(path) for path in paths] if paths is not None else candidate_auth_files()
    return next((path for path in candidates if path.exists()), None)


def build_codex_login_command() -> list[str]:
    return ["npx", "@openai/codex", "login"]


def build_proxy_command(env: dict[str, str] | None = None) -> list[str]:
    values = env if env is not None else os.environ
    models = values.get("OPENAI_OAUTH_MODELS") or ",".join(DEFAULT_OPENAI_OAUTH_MODELS)
    return ["npm", "run", "llm:proxy", "--", "--models", models]


def _start_process(
    command: list[str],
    *,
    cwd: str | Path | None = None,
    popen: Callable[..., Any] = subprocess.Popen,
) -> OpenAIOAuthProcess:
    process = popen(command, cwd=Path(cwd) if cwd is not None else None)
    return OpenAIOAuthProcess(pid=process.pid, command=command)


def start_codex_login(
    *,
    cwd: str | Path | None = None,
    popen: Callable[..., Any] = subprocess.Popen,
) -> OpenAIOAuthProcess:
    return _start_process(build_codex_login_command(), cwd=cwd, popen=popen)


def start_openai_oauth_proxy(
    *,
    cwd: str | Path | None = None,
    popen: Callable[..., Any] = subprocess.Popen,
) -> OpenAIOAuthProcess:
    return _start_process(build_proxy_command(), cwd=cwd, popen=popen)


def check_openai_oauth_proxy(
    *,
    base_url: str | None = None,
    timeout: float = 2.0,
    urlopen: Callable[..., Any] = request.urlopen,
) -> OpenAIOAuthStatus:
    root = (base_url or os.environ.get("OPENAI_OAUTH_BASE_URL") or DEFAULT_OPENAI_OAUTH_BASE_URL).rstrip("/")
    models_url = f"{root}/models"
    try:
        req = request.Request(models_url, method="GET")
        with urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return OpenAIOAuthStatus(
            connected=False,
            message=f"openai-oauth proxy is not reachable: {exc}",
        )

    models = [
        str(item["id"])
        for item in payload.get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]
    return OpenAIOAuthStatus(
        connected=True,
        message="openai-oauth proxy is reachable.",
        models=models,
    )
