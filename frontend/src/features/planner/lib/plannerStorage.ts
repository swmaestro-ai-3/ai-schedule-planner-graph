import type { PlannerDraft } from "../types/planner";

const STORAGE_KEY = "nextplan.calendarDraft";

type DraftStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function browserStorage(): DraftStorage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function loadStoredDraft(storage: DraftStorage | null = browserStorage()): PlannerDraft | null {
  if (!storage) return null;
  const rawValue = storage.getItem(STORAGE_KEY);
  if (!rawValue) return null;
  try {
    return JSON.parse(rawValue) as PlannerDraft;
  } catch {
    storage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function saveStoredDraft(
  draft: PlannerDraft,
  storage: DraftStorage | null = browserStorage(),
): void {
  if (!storage) return;
  storage.setItem(STORAGE_KEY, JSON.stringify(draft));
}

export function clearStoredDraft(storage: DraftStorage | null = browserStorage()): void {
  if (!storage) return;
  storage.removeItem(STORAGE_KEY);
}
