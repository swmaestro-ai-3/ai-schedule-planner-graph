import { Bot, Check, LoaderCircle, RotateCcw, Send, X } from "lucide-react";
import { useState } from "react";
import type { CreatePlanInput, PlannerDraft, ReplanInput, ScheduleItem } from "../types/planner";

interface AgentChatProps {
  open: boolean;
  busy: boolean;
  hasDraft: boolean;
  draft: PlannerDraft | null;
  onOpenChange: (open: boolean) => void;
  onCreateProposal: (input: CreatePlanInput) => Promise<AgentProposalResult>;
  onReplanProposal: (baseDraft: PlannerDraft, input: ReplanInput) => Promise<AgentProposalResult>;
  onCommitDraft: (draft: PlannerDraft) => void;
}

export interface AgentProposalResult {
  draft: PlannerDraft | null;
  error?: string;
}

interface ChatMessage {
  role: "agent" | "user";
  text: string;
}

const initialAgentMessage: ChatMessage = {
  role: "agent",
  text: "원하는 일정을 말해 주세요. 먼저 초안으로 보여드리고, 확인 후 캘린더에 반영합니다.",
};

const createBusyCopy = {
  title: "일정안을 쓰는 중",
  detail: "요청을 구조화하고 초안으로 보여줄 캘린더 배치를 준비하고 있습니다.",
};

const replanBusyCopy = {
  title: "수정안을 쓰는 중",
  detail: "현재 제안과 피드백을 비교해서 반영 전 수정안을 준비하고 있습니다.",
};

const MIN_TYPING_MS = 650;

export const agentResetButtonLabel = "채팅 초기화";

export function agentResetState() {
  return {
    text: "",
    pendingDraft: null,
    messages: [{ ...initialAgentMessage }],
  };
}

export function agentBusyCopy(hasDraft: boolean) {
  return hasDraft ? replanBusyCopy : createBusyCopy;
}

export function agentProposalSummary(draft: PlannerDraft) {
  const fixedCount = draft.items.filter((item) => item.type === "fixed").length;
  const taskCount = draft.items.filter((item) => item.type === "task").length;
  return `고정 일정 ${fixedCount}개, 작업 ${taskCount}개를 배치한 초안입니다.`;
}

export function agentPreviewItems(draft: PlannerDraft, limit = 3) {
  return draft.items.slice(0, limit).map((item) => formatPreviewItem(item));
}

function formatPreviewItem(item: ScheduleItem) {
  const dayLabels = ["월", "화", "수", "목", "금", "토", "일"];
  return `${dayLabels[item.dayIndex] ?? "일정"} ${item.start}-${item.end} ${item.title}`;
}

function wait(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export function AgentChat({
  open,
  busy,
  hasDraft,
  draft,
  onOpenChange,
  onCreateProposal,
  onReplanProposal,
  onCommitDraft,
}: AgentChatProps) {
  const [text, setText] = useState("");
  const [typing, setTyping] = useState(false);
  const [pendingDraft, setPendingDraft] = useState<PlannerDraft | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>(() => agentResetState().messages);

  const workingDraft = pendingDraft ?? draft;
  const hasWorkingDraft = Boolean(workingDraft);
  const isWorking = busy || typing;
  const taskCount = workingDraft?.items.filter((item) => item.type === "task").length ?? 0;
  const busyCopy = agentBusyCopy(hasWorkingDraft);

  const submit = async () => {
    const value = text.trim();
    if (!value || isWorking) return;

    setMessages((current) => [...current, { role: "user", text: value }]);
    setText("");
    setTyping(true);

    const startedAt = Date.now();
    const baseDraft = pendingDraft ?? draft;
    const result = baseDraft
      ? await onReplanProposal(baseDraft, { reason: value, snoozeDays: 1 })
      : await onCreateProposal({ mode: "natural", text: value, bufferRatio: 15 });

    const remainingDelay = Math.max(0, MIN_TYPING_MS - (Date.now() - startedAt));
    if (remainingDelay > 0) {
      await wait(remainingDelay);
    }

    setTyping(false);

    if (!result.draft) {
      setMessages((current) => [
        ...current,
        {
          role: "agent",
          text:
            result.error ||
            "초안을 만들지 못했습니다. 원하는 요일, 시간, 작업명을 조금 더 구체적으로 알려주세요.",
        },
      ]);
      return;
    }

    setPendingDraft(result.draft);
    setMessages((current) => [
      ...current,
      {
        role: "agent",
        text: "초안을 준비했습니다. 아직 캘린더에는 반영하지 않았습니다. 확인 후 확정해 주세요.",
      },
    ]);
  };

  const commitPendingDraft = () => {
    if (!pendingDraft) return;
    onCommitDraft(pendingDraft);
    setPendingDraft(null);
    setMessages((current) => [
      ...current,
      {
        role: "agent",
        text: "확정했습니다. 이제 캘린더에 반영했습니다.",
      },
    ]);
  };

  const resetChat = () => {
    if (isWorking) return;
    const nextState = agentResetState();
    setText(nextState.text);
    setPendingDraft(nextState.pendingDraft);
    setMessages(nextState.messages);
  };

  return (
    <div className={`agent-chat ${isWorking ? "is-busy" : ""}`}>
      {open && (
        <section className="agent-panel" aria-label="AI 일정 에이전트" aria-busy={isWorking}>
          <header>
            <div>
              <strong>AI 일정 에이전트</strong>
              <span>
                {isWorking
                  ? busyCopy.title
                  : pendingDraft
                    ? "확정 대기 중"
                    : hasDraft
                      ? `${taskCount}개 작업 조율 가능`
                      : "새 일정 조율"}
              </span>
            </div>
            <div className="agent-header-actions">
              <button
                type="button"
                aria-label={agentResetButtonLabel}
                title={agentResetButtonLabel}
                onClick={resetChat}
                disabled={isWorking}
              >
                <RotateCcw size={15} />
              </button>
              <button type="button" aria-label="닫기" onClick={() => onOpenChange(false)}>
                <X size={16} />
              </button>
            </div>
          </header>
          <div className="agent-messages" aria-live="polite">
            {messages.map((message, index) => (
              <div className={`agent-message ${message.role}`} key={`${message.role}-${index}`}>
                {message.text}
              </div>
            ))}
            {isWorking && (
              <div className="agent-message agent agent-typing" aria-label="AI가 응답을 작성 중">
                <span className="typing-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <span>{busyCopy.title}</span>
              </div>
            )}
          </div>

          {pendingDraft && (
            <article className="agent-proposal" aria-label="반영 전 일정 초안">
              <div>
                <span>반영 전 초안</span>
                <strong>{agentProposalSummary(pendingDraft)}</strong>
              </div>
              <ul>
                {agentPreviewItems(pendingDraft).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <div className="agent-proposal-actions">
                <button className="button primary" type="button" onClick={commitPendingDraft} disabled={isWorking}>
                  <Check size={16} />
                  캘린더에 반영
                </button>
                <button
                  className="button ghost"
                  type="button"
                  onClick={() => setText("이 초안에서 ")}
                  disabled={isWorking}
                >
                  더 조율하기
                </button>
              </div>
            </article>
          )}

          <form
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={
                hasWorkingDraft
                  ? "예: 이 초안에서 기획서 작성은 내일로 미뤄줘"
                  : "예: 매일 23시에 회고 1시간 넣어줘"
              }
              rows={3}
              disabled={isWorking}
            />
            <button className="button primary" type="submit" disabled={isWorking || !text.trim()}>
              {isWorking ? (
                <span className="agent-spinner">
                  <LoaderCircle size={16} />
                </span>
              ) : (
                <Send size={16} />
              )}
              {isWorking ? "작성 중" : pendingDraft ? "수정 요청" : "보내기"}
            </button>
          </form>
        </section>
      )}
      <button
        className="agent-fab"
        type="button"
        aria-label="AI 일정 에이전트 열기"
        onClick={() => onOpenChange(!open)}
      >
        {isWorking ? (
          <span className="agent-spinner">
            <LoaderCircle size={24} />
          </span>
        ) : (
          <Bot size={24} />
        )}
      </button>
    </div>
  );
}
