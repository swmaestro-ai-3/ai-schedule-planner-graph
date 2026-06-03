import { describe, expect, it } from "vitest";
import { clearStoredDraft, loadStoredDraft, saveStoredDraft } from "./plannerStorage";
import type { PlannerDraft } from "../types/planner";

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  };
}

const draft: PlannerDraft = {
  weekStart: "2026-06-01",
  weekLabel: "2026.06.01 - 06.07",
  reason: "배치 완료",
  items: [],
  validation: [],
  replanCount: 0,
};

describe("planner local storage", () => {
  it("saves and loads the latest calendar draft", () => {
    const storage = memoryStorage();

    saveStoredDraft(draft, storage);

    expect(loadStoredDraft(storage)).toEqual(draft);
  });

  it("returns null for corrupt storage and clears drafts", () => {
    const storage = memoryStorage();
    storage.setItem("nextplan.calendarDraft", "{");

    expect(loadStoredDraft(storage)).toBeNull();

    saveStoredDraft(draft, storage);
    clearStoredDraft(storage);

    expect(loadStoredDraft(storage)).toBeNull();
  });
});
