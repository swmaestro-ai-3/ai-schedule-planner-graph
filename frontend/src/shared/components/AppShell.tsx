import { Terminal, WandSparkles } from "lucide-react";
import type { ReactNode } from "react";
import { plannerSteps } from "../../features/planner/data/plannerSteps";
import type { PlannerStepId } from "../../features/planner/types/planner";

interface AppShellProps {
  activeStep: PlannerStepId;
  aiConnected: boolean;
  aiConnecting: boolean;
  onGoHome: () => void;
  onConnectAi: () => void;
  children: ReactNode;
}

export const homeButtonLabel = "시작 화면으로 돌아가기";

export function aiStatusButtonLabel(aiConnected: boolean, aiConnecting = false) {
  if (aiConnecting) return "AI 연결 확인 중";
  return aiConnected ? "AI 연결됨, 클릭해서 상태 다시 확인" : "AI 미연결, 클릭해서 연결";
}

export function AppShell({
  activeStep,
  aiConnected,
  aiConnecting,
  onGoHome,
  onConnectAi,
  children,
}: AppShellProps) {
  const activeIndex = plannerSteps.find((step) => step.id === activeStep)?.index ?? 1;

  return (
    <div className="app-shell">
      <header className="global-header">
        <button
          className="brand brand-button"
          type="button"
          aria-label={homeButtonLabel}
          onClick={onGoHome}
        >
          <div className="brand-icon">
            <WandSparkles size={18} />
          </div>
          <div>
            <h1>NextPlan AI</h1>
            <p>주간 일정 자동 배치</p>
          </div>
        </button>

        <nav className="stepper" aria-label="작업 단계">
          {plannerSteps.map((step) => {
            const state =
              step.index < activeIndex
                ? "complete"
                : step.index === activeIndex
                  ? "active"
                  : "upcoming";
            return (
              <div className={`stepper-item ${state}`} key={step.id}>
                <span>{step.index}</span>
                <strong>{step.label}</strong>
              </div>
            );
          })}
        </nav>

        <div className="header-actions">
          <button
            className={`status-pill ${aiConnected ? "connected" : ""}`}
            type="button"
            aria-label={aiStatusButtonLabel(aiConnected, aiConnecting)}
            disabled={aiConnecting}
            onClick={onConnectAi}
          >
            <span />
            AI {aiConnecting ? "확인 중" : aiConnected ? "연결됨" : "미연결"}
          </button>
          <button className="ghost-icon-button" type="button" aria-label="로그">
            <Terminal size={16} />
          </button>
        </div>
      </header>
      {children}
    </div>
  );
}
