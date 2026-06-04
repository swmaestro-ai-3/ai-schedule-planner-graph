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

  it("includes recent conversation context in parse requests before a draft exists", () => {
    const request = buildResponseRequest(
      {
        task: "parse_day_plan",
        prompt: "사용자의 자연어 일정을 DayPlanInput JSON으로만 구조화한다.",
        input: "그럼 월요일 운동 1시간 넣어줘",
        reference_date: "2026-06-01",
        timezone: "Asia/Seoul",
        conversation: [
          { role: "user", text: "어떤 식으로 말하면 돼?" },
          { role: "agent", text: "요일, 시간, 소요 시간을 알려주면 됩니다." },
        ],
        output_schema: {
          type: "object",
          required: [],
          properties: {
            day_plan: { type: "object" },
            assistant_message: { type: "string" },
          },
        },
      },
      "gpt-test",
    );

    const text = request.input[0].content[0].text;

    assert.match(text, /Conversation:/);
    assert.match(text, /어떤 식으로 말하면 돼\?/);
    assert.match(text, /요일, 시간, 소요 시간을 알려주면 됩니다/);
    assert.match(text, /그럼 월요일 운동 1시간 넣어줘/);
    assert.match(text, /assistant_message/);
  });
});
