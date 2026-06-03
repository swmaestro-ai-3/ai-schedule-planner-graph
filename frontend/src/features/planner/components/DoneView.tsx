import { Copy, RotateCcw } from "lucide-react";
import type { PlannerDraft } from "../types/planner";

interface DoneViewProps {
  draft: PlannerDraft;
  onReset: () => void;
}

export function DoneView({ draft, onReset }: DoneViewProps) {
  const taskCount = draft.items.filter((item) => item.type === "task").length;

  return (
    <main className="view done-view">
      <section className="done-panel">
        <div className="done-mark">✓</div>
        <span>완료</span>
        <h2>일정 확정</h2>
        <dl>
          <div>
            <dt>주간</dt>
            <dd>{draft.weekLabel}</dd>
          </div>
          <div>
            <dt>작업</dt>
            <dd>{taskCount}개</dd>
          </div>
          <div>
            <dt>수정</dt>
            <dd>{draft.replanCount}회</dd>
          </div>
        </dl>
        <div className="done-actions">
          <button className="button subtle" type="button" onClick={onReset}>
            <RotateCcw size={16} />
            처음부터
          </button>
          <button className="button primary" type="button">
            <Copy size={16} />
            복사
          </button>
        </div>
      </section>
    </main>
  );
}
