import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sidecar_returns_fake_response_from_env():
    fake_response = {"day_plan": {"date": "2026-06-03"}}
    env = {
        **os.environ,
        "LLM_SIDECAR_FAKE_RESPONSE": json.dumps(fake_response),
    }

    completed = subprocess.run(
        ["node", "llm_sidecar/openai_oauth_client.mjs"],
        cwd=ROOT,
        input=json.dumps({"task": "parse_day_plan"}),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )

    assert json.loads(completed.stdout) == fake_response


def test_package_manifest_keeps_openai_oauth_proxy_script():
    package_data = json.loads((ROOT / "package.json").read_text())

    assert package_data["dependencies"]["openai-oauth"] == "1.0.2"
    assert package_data["scripts"]["llm:proxy"] == "openai-oauth"
    assert package_data["scripts"]["llm:sidecar"] == "node llm_sidecar/openai_oauth_client.mjs"


def test_sidecar_readme_documents_agpl_and_token_risk():
    readme = (ROOT / "llm_sidecar" / "README.md").read_text()

    assert "AGPL-3.0-only" in readme
    assert "auth.json" in readme
    assert "not affiliated" in readme
