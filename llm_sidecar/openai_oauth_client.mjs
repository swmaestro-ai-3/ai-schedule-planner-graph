import process from "node:process";

export async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

export function printJson(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function formatPrompt(payload) {
  const sections = [];
  if (payload.prompt) {
    sections.push(String(payload.prompt).trim());
  }
  if (payload.reference_date || payload.timezone) {
    sections.push(
      `Context: ${JSON.stringify(
        {
          reference_date: payload.reference_date,
          timezone: payload.timezone,
        },
        null,
        2,
      )}`,
    );
  }
  if (payload.current_state) {
    sections.push(`Current state: ${JSON.stringify(payload.current_state, null, 2)}`);
  }
  if (payload.output_schema) {
    sections.push(`Output schema: ${JSON.stringify(payload.output_schema, null, 2)}`);
  }
  sections.push(`User input: ${JSON.stringify(payload.input ?? payload, null, 2)}`);
  return sections.join("\n\n");
}

export function buildResponseRequest(
  payload,
  model = process.env.OPENAI_OAUTH_MODEL ?? "gpt-5.4",
) {
  return {
    model,
    stream: true,
    input: [
      {
        role: "user",
        content: [
          {
            type: "input_text",
            text: formatPrompt(payload),
          },
        ],
      },
    ],
    text: {
      format: {
        type: "json_object",
      },
    },
  };
}

export function extractOutputTextFromResponse(data) {
  if (typeof data.output_text === "string") {
    return data.output_text;
  }

  const content = data.output
    ?.flatMap((item) => item.content ?? [])
    ?.find((part) => part.type === "output_text" && typeof part.text === "string");
  return content?.text;
}

export function parseSseOutputText(streamText) {
  const deltas = [];
  const outputTextDone = [];
  const itemDoneTexts = [];
  for (const block of streamText.split(/\n\n+/)) {
    const dataLines = block
      .split(/\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice("data:".length).trim())
      .filter((line) => line && line !== "[DONE]");
    if (dataLines.length === 0) {
      continue;
    }

    let event;
    try {
      event = JSON.parse(dataLines.join("\n"));
    } catch {
      continue;
    }

    if (event.type === "response.output_text.done" && typeof event.text === "string") {
      outputTextDone.push(event.text);
    } else if (
      event.type === "response.output_text.delta" &&
      typeof event.delta === "string"
    ) {
      deltas.push(event.delta);
    } else if (event.type === "response.output_item.done" && Array.isArray(event.item?.content)) {
      for (const part of event.item.content) {
        if (part.type === "output_text" && typeof part.text === "string") {
          itemDoneTexts.push(part.text);
        }
      }
    }
  }

  if (outputTextDone.length > 0) {
    return outputTextDone.join("");
  }
  if (itemDoneTexts.length > 0) {
    return itemDoneTexts.join("");
  }
  return deltas.join("");
}

export async function main() {
  const rawInput = await readStdin();
  const payload = rawInput ? JSON.parse(rawInput) : {};

  if (process.env.LLM_SIDECAR_FAKE_RESPONSE) {
    printJson(JSON.parse(process.env.LLM_SIDECAR_FAKE_RESPONSE));
    return;
  }

  const baseUrl = process.env.OPENAI_OAUTH_BASE_URL ?? "http://127.0.0.1:10531/v1";
  const response = await fetch(`${baseUrl}/responses`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(buildResponseRequest(payload)),
  });

  const body = await response.text();
  if (!response.ok) {
    throw new Error(`openai-oauth proxy request failed: ${response.status} ${body}`);
  }

  let outputText = parseSseOutputText(body);
  if (!outputText) {
    outputText = extractOutputTextFromResponse(JSON.parse(body));
  }

  if (!outputText) {
    throw new Error("openai-oauth proxy response did not include output text");
  }

  printJson(JSON.parse(outputText));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exit(1);
  });
}
