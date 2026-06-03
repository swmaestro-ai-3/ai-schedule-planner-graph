import { ArrowLeft, Send } from "lucide-react";
import { useState } from "react";
import type { PlannerDraft, ReplanInput } from "../types/planner";

interface ReviewViewProps {
  draft: PlannerDraft;
  onBack: () => void;
  onSubmit: (input: ReplanInput) => void;
}

export function ReviewView({ draft, onBack, onSubmit }: ReviewViewProps) {
  const [reason, setReason] = useState("오후 운동은 하루 뒤로 미뤄줘.");
  const [snoozeTaskId, setSnoozeTaskId] = useState("");
  const [snoozeDays, setSnoozeDays] = useState(1);
  const taskOptions = draft.items.filter((item) => item.type === "task");

  return (
    <main className="view review-view">
      <section className="review-panel">
        <div className="view-heading">
          <span>04 / 수정</span>
          <h2>수정 요청</h2>
          <p>검토 결과와 바꿀 점만 남깁니다.</p>
        </div>

        <div className="validation-list">
          {draft.validation.map((row) => (
            <div className="validation-row" key={row.label}>
              <strong>{row.label}</strong>
              <span className={row.status}>{row.detail}</span>
            </div>
          ))}
        </div>

        <label className="field-label" htmlFor="feedback">
          요청
        </label>
        <textarea
          id="feedback"
          rows={5}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />

        <div className="snooze-grid">
          <label>
            미룰 작업
            <select value={snoozeTaskId} onChange={(event) => setSnoozeTaskId(event.target.value)}>
              <option value="">선택 안 함</option>
              {taskOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            기간
            <input
              type="number"
              min={1}
              max={6}
              value={snoozeDays}
              onChange={(event) => setSnoozeDays(Number(event.target.value))}
            />
          </label>
        </div>

        <div className="review-actions">
          <button className="button subtle" type="button" onClick={onBack}>
            <ArrowLeft size={16} />
            제안으로
          </button>
          <button
            className="button warning"
            type="button"
            disabled={!reason.trim()}
            onClick={() => onSubmit({ reason, snoozeTaskId, snoozeDays })}
          >
            <Send size={16} />
            다시 만들기
          </button>
        </div>
      </section>
    </main>
  );
}
