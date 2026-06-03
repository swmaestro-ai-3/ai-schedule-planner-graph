import { Terminal, WandSparkles } from "lucide-react";
import type { ReactNode } from "react";
import { plannerSteps } from "../../features/planner/data/plannerSteps";
import type { PlannerStepId } from "../../features/planner/types/planner";

interface AppShellProps {
  activeStep: PlannerStepId;
  aiConnected: boolean;
  children: ReactNode;
}

export function AppShell({ activeStep, aiConnected, children }: AppShellProps) {
  const activeIndex = plannerSteps.find((step) => step.id === activeStep)?.index ?? 1;

  return (
    <div className="app-shell">
      <header className="global-header">
        <div className="brand">
          <div className="brand-icon">
            <WandSparkles size={18} />
          </div>
          <div>
            <h1>NextPlan AI</h1>
            <p>주간 일정 자동 배치</p>
          </div>
        </div>

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
          <div className={`status-pill ${aiConnected ? "connected" : ""}`}>
            <span />
            AI {aiConnected ? "연결됨" : "미연결"}
          </div>
          <button className="ghost-icon-button" type="button" aria-label="로그">
            <Terminal size={16} />
          </button>
        </div>
      </header>
      {children}
    </div>
  );
}
