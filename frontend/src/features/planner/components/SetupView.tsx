import { ChevronRight, Link, SlidersHorizontal } from "lucide-react";

interface SetupViewProps {
  aiConnected: boolean;
  onConnect: () => void;
  onNext: () => void;
}

export function SetupView({ aiConnected, onConnect, onNext }: SetupViewProps) {
  return (
    <main className="view setup-view">
      <section className="view-heading centered">
        <span>01 / 시작</span>
        <h2>하루 기준 설정</h2>
        <p>활동 시간과 AI 연결 상태만 확인합니다.</p>
      </section>

      <div className="setup-grid">
        <article className="setup-panel">
          <div className="panel-title-row">
            <div className="panel-kicker">
              <Link size={16} />
              AI 연결
            </div>
            <span className={`mini-badge ${aiConnected ? "ok" : ""}`}>
              {aiConnected ? "완료" : "필요"}
            </span>
          </div>
          <h3>OpenAI 계정</h3>
          <p>연결되면 자연어 일정 해석과 재배치 품질이 좋아집니다.</p>
          {!aiConnected && (
            <button className="button dark full" type="button" onClick={onConnect}>
              <Link size={16} />
              OpenAI 연결
            </button>
          )}
        </article>

        <article className="setup-panel">
          <div className="panel-title-row">
            <div className="panel-kicker muted">
              <SlidersHorizontal size={16} />
              시간 기준
            </div>
          </div>
          <h3>09:00 - 23:59</h3>
          <div className="time-grid">
            <label>
              시작
              <input type="time" defaultValue="09:00" />
            </label>
            <label>
              종료
              <input type="time" defaultValue="23:59" />
            </label>
          </div>
        </article>
      </div>

      <div className="center-action">
        <button className="button primary large" type="button" onClick={onNext}>
          시작하기
          <ChevronRight size={16} />
        </button>
      </div>
    </main>
  );
}
