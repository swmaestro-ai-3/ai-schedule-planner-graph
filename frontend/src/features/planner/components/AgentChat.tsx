import { Bot, LoaderCircle, Send, X } from "lucide-react";
import { useState } from "react";
import type { CreatePlanInput, PlannerDraft, ReplanInput } from "../types/planner";

interface AgentChatProps {
  open: boolean;
  busy: boolean;
  hasDraft: boolean;
  draft: PlannerDraft | null;
  onOpenChange: (open: boolean) => void;
  onCreatePlan: (input: CreatePlanInput) => Promise<boolean>;
  onReplan: (input: ReplanInput) => Promise<boolean>;
}

interface ChatMessage {
  role: "agent" | "user";
  text: string;
}

const createBusyCopy = {
  title: "일정안을 만드는 중",
  detail: "요청을 구조화하고 가용 시간에 맞춰 캘린더 블록을 배치하고 있습니다.",
};

const replanBusyCopy = {
  title: "요청을 반영하는 중",
  detail: "기존 일정과 피드백을 비교해서 주간 캘린더를 다시 배치하고 있습니다.",
};

export function agentBusyCopy(hasDraft: boolean) {
  return hasDraft ? replanBusyCopy : createBusyCopy;
}

export function AgentChat({
  open,
  busy,
  hasDraft,
  draft,
  onOpenChange,
  onCreatePlan,
  onReplan,
}: AgentChatProps) {
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "agent",
      text: "일정 생성이나 수정 요청을 입력하세요.",
    },
  ]);

  const submit = async () => {
    const value = text.trim();
    if (!value || busy) return;
    setMessages((current) => [...current, { role: "user", text: value }]);
    setText("");

    if (hasDraft) {
      const ok = await onReplan({ reason: value, snoozeDays: 1 });
      setMessages((current) => [
        ...current,
        {
          role: "agent",
          text: ok
            ? "요청을 반영해 다시 배치했습니다."
            : "요청을 처리하지 못했습니다. 입력을 조금 바꿔 다시 보내주세요.",
        },
      ]);
      return;
    }

    const ok = await onCreatePlan({ mode: "natural", text: value, bufferRatio: 15 });
    setMessages((current) => [
      ...current,
        {
          role: "agent",
          text: ok
            ? "일정안을 만들었습니다."
            : "일정안을 만들지 못했습니다. 요청을 조금 더 구체적으로 입력해주세요.",
      },
    ]);
  };

  const taskCount = draft?.items.filter((item) => item.type === "task").length ?? 0;
  const busyCopy = agentBusyCopy(hasDraft);

  return (
    <div className={`agent-chat ${busy ? "is-busy" : ""}`}>
      {open && (
        <section className="agent-panel" aria-label="AI 일정 에이전트" aria-busy={busy}>
          <header>
            <div>
              <strong>AI 일정 에이전트</strong>
              <span>
                {busy ? busyCopy.title : hasDraft ? `${taskCount}개 작업 수정 가능` : "새 일정 생성"}
              </span>
            </div>
            <button type="button" aria-label="닫기" onClick={() => onOpenChange(false)}>
              <X size={16} />
            </button>
          </header>
          <div className="agent-messages" aria-live="polite">
            {messages.map((message, index) => (
              <div className={`agent-message ${message.role}`} key={`${message.role}-${index}`}>
                {message.text}
              </div>
            ))}
            {busy && (
              <div className="agent-message agent agent-working">
                <span className="agent-working-row">
                  <span className="agent-spinner">
                    <LoaderCircle size={15} />
                  </span>
                  {busyCopy.title}
                </span>
                <span>{busyCopy.detail}</span>
                <span className="agent-progress" aria-hidden="true">
                  <span />
                </span>
              </div>
            )}
          </div>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={hasDraft ? "예: 기획서 작성 내일로 미뤄줘" : "예: 매일 23시에 회고 1시간 넣어줘"}
              rows={3}
              disabled={busy}
            />
            <button className="button primary" type="submit" disabled={busy || !text.trim()}>
              {busy ? (
                <span className="agent-spinner">
                  <LoaderCircle size={16} />
                </span>
              ) : (
                <Send size={16} />
              )}
              {busy ? "작업 중" : "보내기"}
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
        {busy ? (
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
