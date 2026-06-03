import { ArrowLeft, CheckCircle2, SlidersHorizontal } from "lucide-react";
import { CalendarWeek } from "./CalendarWeek";
import type { PlannerDraft } from "../types/planner";

interface ProposalViewProps {
  draft: PlannerDraft;
  onBack: () => void;
  onReview: () => void;
  onApprove: () => void;
}

export function ProposalView({ draft, onBack, onReview, onApprove }: ProposalViewProps) {
  return (
    <main className="view proposal-view">
      <div className="proposal-toolbar">
        <div>
          <span className="live-dot" />
          <h2>제안 확인</h2>
          <p>{draft.weekLabel}</p>
        </div>
        <div className="toolbar-actions">
          <button className="button subtle" type="button" onClick={onReview}>
            <SlidersHorizontal size={16} />
            수정하기
          </button>
          <button className="button success" type="button" onClick={onApprove}>
            <CheckCircle2 size={16} />
            확정
          </button>
        </div>
      </div>

      <section className="reason-panel">
        <h3>배치 기준</h3>
        <p>{draft.reason}</p>
      </section>

      <CalendarWeek weekStart={draft.weekStart} items={draft.items} />

      <div className="bottom-bar">
        <button className="text-button" type="button" onClick={onBack}>
          <ArrowLeft size={16} />
          다시 입력
        </button>
        <div className="legend">
          <span className="legend-fixed" /> 고정
          <span className="legend-task" /> 작업
        </div>
      </div>
    </main>
  );
}
