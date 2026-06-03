import { CalendarDays, Keyboard, WandSparkles } from "lucide-react";
import { useState } from "react";
import type { CreatePlanInput, InputMode } from "../types/planner";

interface InputViewProps {
  busy: boolean;
  onCreatePlan: (input: CreatePlanInput) => void;
}

export function InputView({ busy, onCreatePlan }: InputViewProps) {
  const [mode, setMode] = useState<InputMode>("natural");
  const [text, setText] = useState(
    "월요일부터 금요일까지 매일 15시에 운동 1시간 넣어줘. 매일 오후 11시에는 하루 회고도 배치해줘.",
  );
  const [bufferRatio, setBufferRatio] = useState(15);

  const submitNatural = () => {
    if (!text.trim()) return;
    onCreatePlan({ mode: "natural", text, bufferRatio });
  };

  const submitStructured = () => {
    onCreatePlan({
      mode: "structured",
      bufferRatio,
      fixedEvents: ["월 09:00 팀 미팅"],
      tasks: ["기획서 작성 120분", "코드 리뷰 90분", "개발 공부 120분"],
    });
  };

  return (
    <main className="view split-view">
      <section className="input-pane">
        <div className="view-heading">
          <span>02 / 입력</span>
          <h2>일정 입력</h2>
          <p>말로 쓰거나 항목으로 적습니다.</p>
        </div>

        <div className="segmented-control" role="tablist" aria-label="입력 방식">
          <button
            className={mode === "natural" ? "active" : ""}
            type="button"
            onClick={() => setMode("natural")}
          >
            <Keyboard size={16} />
            자유 입력
          </button>
          <button
            className={mode === "structured" ? "active" : ""}
            type="button"
            onClick={() => setMode("structured")}
          >
            <CalendarDays size={16} />
            직접 입력
          </button>
        </div>

        {mode === "natural" ? (
          <section className="input-section">
            <label className="field-label" htmlFor="natural-plan">
              요청
            </label>
            <textarea
              id="natural-plan"
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={8}
            />
            <BufferSlider value={bufferRatio} onChange={setBufferRatio} />
            <button className="button primary full" type="button" onClick={submitNatural} disabled={busy}>
              <WandSparkles size={16} />
              일정 만들기
            </button>
          </section>
        ) : (
          <section className="input-section">
            <BufferSlider value={bufferRatio} onChange={setBufferRatio} />
            <div className="structured-list">
              <h3>고정 일정</h3>
              <div className="inline-row">월 09:00 팀 미팅</div>
              <h3>작업</h3>
              <div className="inline-row">기획서 작성 · 120분 · High</div>
              <div className="inline-row">코드 리뷰 · 90분 · Medium</div>
              <div className="inline-row">개발 공부 · 120분 · Medium</div>
            </div>
            <button className="button dark full" type="button" onClick={submitStructured} disabled={busy}>
              <CalendarDays size={16} />
              일정 만들기
            </button>
          </section>
        )}
      </section>

      <aside className="input-aside">
        <h3>입력 원칙</h3>
        <ul>
          <li>고정 일정은 옮기지 않습니다.</li>
          <li>작업은 주간 가용 시간에 분산합니다.</li>
          <li>빈 시간은 블록으로 채우지 않습니다.</li>
        </ul>
      </aside>
    </main>
  );
}

function BufferSlider({
  value,
  onChange,
}: {
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="range-field">
      <span>
        여유 시간
        <strong>{value}%</strong>
      </span>
      <input
        type="range"
        min="0"
        max="40"
        step="5"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
