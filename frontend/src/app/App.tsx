import { useState } from "react";
import { mockPlannerApi } from "../features/planner/api/plannerApi";
import { DoneView } from "../features/planner/components/DoneView";
import { InputView } from "../features/planner/components/InputView";
import { ProposalView } from "../features/planner/components/ProposalView";
import { ReviewView } from "../features/planner/components/ReviewView";
import { SetupView } from "../features/planner/components/SetupView";
import type {
  CreatePlanInput,
  PlannerDraft,
  PlannerStepId,
  ReplanInput,
} from "../features/planner/types/planner";
import { AppShell } from "../shared/components/AppShell";

export function App() {
  const [activeStep, setActiveStep] = useState<PlannerStepId>("setup");
  const [aiConnected, setAiConnected] = useState(false);
  const [draft, setDraft] = useState<PlannerDraft | null>(null);
  const [busy, setBusy] = useState(false);

  const createPlan = async (input: CreatePlanInput) => {
    setBusy(true);
    const next = await mockPlannerApi.createPlan(input);
    setDraft(next);
    setBusy(false);
    setActiveStep("proposal");
  };

  const replan = async (input: ReplanInput) => {
    if (!draft) return;
    setBusy(true);
    const next = await mockPlannerApi.replan(draft, input);
    setDraft(next);
    setBusy(false);
    setActiveStep("proposal");
  };

  const reset = () => {
    setDraft(null);
    setActiveStep("setup");
  };

  return (
    <AppShell activeStep={activeStep} aiConnected={aiConnected}>
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
          onReview={() => setActiveStep("review")}
          onApprove={() => setActiveStep("done")}
        />
      )}
      {activeStep === "review" && draft && (
        <ReviewView draft={draft} onBack={() => setActiveStep("proposal")} onSubmit={replan} />
      )}
      {activeStep === "done" && draft && <DoneView draft={draft} onReset={reset} />}
    </AppShell>
  );
}
