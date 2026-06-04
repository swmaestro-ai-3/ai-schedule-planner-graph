import { useEffect, useState } from "react";
import { httpPlannerApi } from "../features/planner/api/plannerApi";
import { AgentChat } from "../features/planner/components/AgentChat";
import { DoneView } from "../features/planner/components/DoneView";
import { GraphView } from "../features/planner/components/GraphView";
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

function wait(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export function App() {
  const [draft, setDraft] = useState<PlannerDraft | null>(() => loadStoredDraft());
  const [activeStep, setActiveStep] = useState<PlannerStepId>(() =>
    loadStoredDraft() ? "proposal" : "setup",
  );
  const [aiConnected, setAiConnected] = useState(false);
  const [aiConnecting, setAiConnecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [agentOpen, setAgentOpen] = useState(false);
  const [graphOpen, setGraphOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    httpPlannerApi
      .getOpenAIStatus()
      .then((status) => {
        if (!cancelled) {
          setAiConnected(status.connected);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAiConnected(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (draft) {
      saveStoredDraft(draft);
    }
  }, [draft]);

  const createPlan = async (input: CreatePlanInput) => {
    setBusy(true);
    setError(null);
    try {
      const result = await httpPlannerApi.createPlan(input);
      if (result.draft) {
        setDraft(result.draft);
        setActiveStep("proposal");
        return true;
      }
      if (result.agentMessage) {
        setNotice(result.agentMessage);
      }
      return false;
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "일정 생성 실패");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const proposePlan = async (input: CreatePlanInput) => {
    setBusy(true);
    setError(null);
    try {
      return await httpPlannerApi.createPlan(input);
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : "일정 생성 실패";
      setError(message);
      return { draft: null, error: message };
    } finally {
      setBusy(false);
    }
  };

  const proposeReplan = async (baseDraft: PlannerDraft, input: ReplanInput) => {
    setBusy(true);
    setError(null);
    try {
      return await httpPlannerApi.replan(baseDraft, input);
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : "재배치 실패";
      setError(message);
      return { draft: null, error: message };
    } finally {
      setBusy(false);
    }
  };

  const commitDraft = (next: PlannerDraft) => {
    setDraft(next);
    setActiveStep("proposal");
    setError(null);
  };

  const connectAi = async () => {
    setAiConnecting(true);
    setError(null);
    setNotice(null);
    try {
      const result = await httpPlannerApi.connectOpenAI();
      let connected = result.connected;
      if (!connected && result.action === "proxy_started") {
        await wait(1200);
        const status = await httpPlannerApi.getOpenAIStatus();
        connected = status.connected;
      }
      setAiConnected(connected);
      setNotice(
        connected && result.action === "proxy_started"
          ? "OpenAI OAuth proxy가 연결되었습니다."
          : result.message,
      );
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : "OpenAI 연결 시작 실패";
      setError(message);
    } finally {
      setAiConnecting(false);
    }
  };

  const reset = () => {
    setDraft(null);
    clearStoredDraft();
    setActiveStep("setup");
    setError(null);
    setNotice(null);
    setAgentOpen(false);
    setGraphOpen(false);
  };

  const openGraph = () => {
    setGraphOpen(true);
    setAgentOpen(false);
  };

  return (
    <AppShell
      activeStep={activeStep}
      aiConnected={aiConnected}
      aiConnecting={aiConnecting}
      onGoHome={reset}
      onOpenGraph={openGraph}
      onConnectAi={connectAi}
    >
      {error && <div className="app-error" role="alert">{error}</div>}
      {notice && <div className="app-notice" role="status">{notice}</div>}
      {graphOpen && <GraphView onBack={() => setGraphOpen(false)} />}
      {!graphOpen && activeStep === "setup" && (
        <SetupView
          aiConnected={aiConnected}
          aiConnecting={aiConnecting}
          onConnect={connectAi}
          onNext={() => setActiveStep("input")}
        />
      )}
      {!graphOpen && activeStep === "input" && <InputView busy={busy} onCreatePlan={createPlan} />}
      {!graphOpen && activeStep === "proposal" && draft && (
        <ProposalView
          draft={draft}
          onBack={() => setActiveStep("input")}
          onReview={() => setAgentOpen(true)}
          onApprove={() => setActiveStep("done")}
        />
      )}
      {!graphOpen && activeStep === "done" && draft && <DoneView draft={draft} onReset={reset} />}
      <AgentChat
        open={agentOpen}
        busy={busy}
        hasDraft={Boolean(draft)}
        draft={draft}
        onOpenChange={setAgentOpen}
        onCreateProposal={proposePlan}
        onReplanProposal={proposeReplan}
        onCommitDraft={commitDraft}
      />
    </AppShell>
  );
}
