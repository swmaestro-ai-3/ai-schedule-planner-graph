import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { buildResponseRequest } from "./openai_oauth_client.mjs";

describe("openai oauth sidecar prompt", () => {
  it("includes recent conversation context in replan requests", () => {
    const request = buildResponseRequest(
      {
        prompt: "사용자의 거절 사유를 ReplanConstraints JSON으로만 변환한다.",
        input: "그거 오후로 바꿔줘",
        conversation: [
          { role: "user", text: "기획서 작성 내일로 미뤄줘" },
          { role: "agent", text: "초안을 준비했습니다." },
        ],
        current_state: {
          schedule_items: [
            {
              source_id: "report",
              title: "기획서 작성",
              day_offset: 1,
              start_offset: 540,
              end_offset: 660,
            },
          ],
        },
      },
      "gpt-test",
    );

    const text = request.input[0].content[0].text;

    assert.match(text, /Conversation:/);
    assert.match(text, /기획서 작성 내일로 미뤄줘/);
    assert.match(text, /그거 오후로 바꿔줘/);
  });
});
