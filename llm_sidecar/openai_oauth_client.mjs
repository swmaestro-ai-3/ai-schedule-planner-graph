import process from "node:process";

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

function printJson(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

async function main() {
  const rawInput = await readStdin();
  const payload = rawInput ? JSON.parse(rawInput) : {};

  if (process.env.LLM_SIDECAR_FAKE_RESPONSE) {
    printJson(JSON.parse(process.env.LLM_SIDECAR_FAKE_RESPONSE));
    return;
  }

  const baseUrl = process.env.OPENAI_OAUTH_BASE_URL ?? "http://127.0.0.1:10531/v1";
  const model = process.env.OPENAI_OAUTH_MODEL ?? "gpt-5";
  const response = await fetch(`${baseUrl}/responses`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      input: JSON.stringify(payload),
      text: {
        format: {
          type: "json_object",
        },
      },
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`openai-oauth proxy request failed: ${response.status} ${body}`);
  }

  const data = await response.json();
  const outputText =
    data.output_text ??
    data.output?.flatMap((item) => item.content ?? [])
      ?.find((content) => content.type === "output_text")?.text;

  if (!outputText) {
    throw new Error("openai-oauth proxy response did not include output text");
  }

  printJson(JSON.parse(outputText));
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
