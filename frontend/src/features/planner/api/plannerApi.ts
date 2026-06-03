import { defaultDraft, reflectionDraft } from "../data/mockDraft";
import type { CreatePlanInput, PlannerDraft, ReplanInput } from "../types/planner";

function cloneDraft(draft: PlannerDraft): PlannerDraft {
  return {
    ...draft,
    validation: draft.validation.map((row) => ({ ...row })),
    items: draft.items.map((item) => ({ ...item })),
  };
}

export interface PlannerApi {
  createPlan(input: CreatePlanInput): Promise<PlannerDraft>;
  replan(draft: PlannerDraft, input: ReplanInput): Promise<PlannerDraft>;
}

type Fetcher = typeof fetch;

interface HttpPlannerApiOptions {
  baseUrl?: string;
  fetcher?: Fetcher;
}

const defaultBaseUrl =
  import.meta.env.VITE_PLANNER_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8010";

async function postJson<T>(
  baseUrl: string,
  fetcher: Fetcher,
  path: string,
  body: unknown,
): Promise<T> {
  const response = await fetcher(`${baseUrl}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.error || "Planner API request failed");
  }
  return payload as T;
}

export function createHttpPlannerApi(options: HttpPlannerApiOptions = {}): PlannerApi {
  const baseUrl = (options.baseUrl ?? defaultBaseUrl).replace(/\/$/, "");
  const fetcher = options.fetcher ?? fetch;
  return {
    createPlan(input) {
      return postJson<PlannerDraft>(baseUrl, fetcher, "/api/plans", input);
    },
    replan(draft, input) {
      return postJson<PlannerDraft>(baseUrl, fetcher, "/api/replans", {
        draft,
        ...input,
      });
    },
  };
}

export const httpPlannerApi = createHttpPlannerApi();

export const mockPlannerApi: PlannerApi = {
  async createPlan(input) {
    if (input.mode === "natural" && input.text.includes("회고")) {
      return cloneDraft(reflectionDraft);
    }
    return cloneDraft(defaultDraft);
  },

  async replan(draft, input) {
    const next = cloneDraft(draft);
    const snoozed = input.snoozeTaskId
      ? next.items.find((item) => item.id === input.snoozeTaskId)
      : undefined;

    if (snoozed) {
      snoozed.dayIndex = Math.min(6, snoozed.dayIndex + input.snoozeDays);
      snoozed.note = "스누즈 반영";
    }

    return {
      ...next,
      replanCount: next.replanCount + 1,
      lastFeedback: input.reason,
      reason: "피드백과 스누즈 조건을 반영해 다시 배치했습니다.",
      validation: [
        { label: "겹침", status: "ok", detail: "충돌 없음" },
        { label: "여유", status: "ok", detail: "수정 후 유지" },
        { label: "변경", status: "warning", detail: "피드백 반영됨" },
      ],
    };
  },
};
