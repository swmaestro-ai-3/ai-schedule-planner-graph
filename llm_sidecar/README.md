# Node OAuth LLM Sidecar

This sidecar is the contract between the Python planner and the npm
`openai-oauth` proxy.

## Local Flow

Start the OpenAI-compatible OAuth proxy:

```bash
npm run llm:proxy
```

Then send JSON to the sidecar:

```bash
npm run llm:sidecar
```

The sidecar reads one JSON payload from stdin and writes one JSON payload to
stdout. Tests use `LLM_SIDECAR_FAKE_RESPONSE` and do not require OAuth login.

## Credential Storage

`openai-oauth` discovers local Codex or ChatGPT OAuth state such as
`auth.json`. Treat this file as password-equivalent credential material. Do
not commit OAuth state or expose it in hosted services.

## License And Risk

The npm dependency `openai-oauth` is a third-party package licensed as
`AGPL-3.0-only`. It is not affiliated with, endorsed by, or sponsored by
OpenAI. Use it only for local experimentation on trusted machines and review
the dependency before production use.
