import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_node_eval(source: str) -> str:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


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


def test_sidecar_builds_streaming_responses_request_with_input_list():
    stdout = run_node_eval(
        """
        import { buildResponseRequest } from './llm_sidecar/openai_oauth_client.mjs';
        const request = buildResponseRequest({
          task: 'health',
          prompt: '응답은 JSON만 반환한다.',
          input: 'health check',
          output_schema: { type: 'object' }
        });
        console.log(JSON.stringify(request));
        """
    )

    request = json.loads(stdout)
    assert request["model"] == "gpt-5.1"
    assert request["stream"] is True
    assert request["input"][0]["role"] == "user"
    assert request["input"][0]["content"][0]["type"] == "input_text"
    assert "health check" in request["input"][0]["content"][0]["text"]
    assert request["text"]["format"]["type"] == "json_object"


def test_sidecar_extracts_output_text_from_sse_stream():
    stdout = run_node_eval(
        r"""
        import { parseSseOutputText } from './llm_sidecar/openai_oauth_client.mjs';
        const stream = [
          'event: response.output_text.delta',
          'data: {"type":"response.output_text.delta","delta":"{\\"ok\\""}',
          '',
          'event: response.output_text.done',
          'data: {"type":"response.output_text.done","text":"{\\"ok\\":true}"}',
          ''
        ].join('\n');
        console.log(parseSseOutputText(stream));
        """
    )

    assert stdout.strip() == '{"ok":true}'


def test_sidecar_does_not_duplicate_done_text_from_sse_stream():
    stdout = run_node_eval(
        r"""
        import { parseSseOutputText } from './llm_sidecar/openai_oauth_client.mjs';
        const stream = [
          'event: response.output_text.done',
          'data: {"type":"response.output_text.done","text":"{\\"ok\\":true}"}',
          '',
          'event: response.output_item.done',
          'data: {"type":"response.output_item.done","item":{"content":[{"type":"output_text","text":"{\\"ok\\":true}"}]}}',
          ''
        ].join('\n');
        console.log(parseSseOutputText(stream));
        """
    )

    assert stdout.strip() == '{"ok":true}'


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
