import { useEffect, useState } from "react";
import { httpPlannerApi } from "../features/planner/api/plannerApi";
import { AgentChat } from "../features/planner/components/AgentChat";
import { DoneView } from "../features/planner/components/DoneView";
import { InputView } from "../features/planner/components/InputView";
import { ProposalView } from "../features/planner/components/ProposalView";
import { SetupView } from "../features/planner/components/SetupView";
import {
  clearStoredDraft,
  loadStoredDraft,
  saveStoredDraft,
} from "../features/planner/lib/plannerStorage";
import type {
  CreatePlanInput,
  PlannerDraft,
  PlannerStepId,
  ReplanInput,
} from "../features/planner/types/planner";
import { AppShell } from "../shared/components/AppShell";

export function App() {
  const [draft, setDraft] = useState<PlannerDraft | null>(() => loadStoredDraft());
  const [activeStep, setActiveStep] = useState<PlannerStepId>(() =>
    loadStoredDraft() ? "proposal" : "setup",
  );
  const [aiConnected, setAiConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentOpen, setAgentOpen] = useState(false);

  useEffect(() => {
    if (draft) {
      saveStoredDraft(draft);
    }
  }, [draft]);

  const createPlan = async (input: CreatePlanInput) => {
    setBusy(true);
    setError(null);
    try {
      const next = await httpPlannerApi.createPlan(input);
      setDraft(next);
      setActiveStep("proposal");
      return true;
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "일정 생성 실패");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const replan = async (input: ReplanInput) => {
    if (!draft) return false;
    setBusy(true);
    setError(null);
    try {
      const next = await httpPlannerApi.replan(draft, input);
      setDraft(next);
      setActiveStep("proposal");
      return true;
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "재배치 실패");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setDraft(null);
    clearStoredDraft();
    setActiveStep("setup");
    setError(null);
  };

  return (
    <AppShell
      activeStep={activeStep}
      aiConnected={aiConnected}
      onConnectAi={() => setAiConnected(true)}
    >
      {error && <div className="app-error" role="alert">{error}</div>}
      {activeStep === "setup" && (
        <SetupView
          aiConnected={aiConnected}
          onConnect={() => setAiConnected(true)}
          onNext={() => setActiveStep("input")}
        />
      )}
      {activeStep === "input" && <InputView busy={busy} onCreatePlan={createPlan} />}
      {activeStep === "proposal" && draft && (
        <ProposalView
          draft={draft}
          onBack={() => setActiveStep("input")}
          onReview={() => setAgentOpen(true)}
          onApprove={() => setActiveStep("done")}
        />
      )}
      {activeStep === "done" && draft && <DoneView draft={draft} onReset={reset} />}
      <AgentChat
        open={agentOpen}
        busy={busy}
        hasDraft={Boolean(draft)}
        draft={draft}
        onOpenChange={setAgentOpen}
        onCreatePlan={createPlan}
        onReplan={replan}
      />
    </AppShell>
  );
}
