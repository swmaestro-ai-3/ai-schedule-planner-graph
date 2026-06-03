import { Bot, Send, X } from "lucide-react";
import { useState } from "react";
import type { CreatePlanInput, PlannerDraft, ReplanInput } from "../types/planner";

interface AgentChatProps {
  open: boolean;
  busy: boolean;
  hasDraft: boolean;
  draft: PlannerDraft | null;
  onOpenChange: (open: boolean) => void;
  onCreatePlan: (input: CreatePlanInput) => Promise<void>;
  onReplan: (input: ReplanInput) => Promise<void>;
}

interface ChatMessage {
  role: "agent" | "user";
  text: string;
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
      await onReplan({ reason: value, snoozeDays: 1 });
      setMessages((current) => [...current, { role: "agent", text: "요청을 반영해 다시 배치했습니다." }]);
      return;
    }

    await onCreatePlan({ mode: "natural", text: value, bufferRatio: 15 });
    setMessages((current) => [...current, { role: "agent", text: "일정안을 만들었습니다." }]);
  };

  const taskCount = draft?.items.filter((item) => item.type === "task").length ?? 0;

  return (
    <div className="agent-chat">
      {open && (
        <section className="agent-panel" aria-label="AI 일정 에이전트">
          <header>
            <div>
              <strong>AI 일정 에이전트</strong>
              <span>{hasDraft ? `${taskCount}개 작업 수정 가능` : "새 일정 생성"}</span>
            </div>
            <button type="button" aria-label="닫기" onClick={() => onOpenChange(false)}>
              <X size={16} />
            </button>
          </header>
          <div className="agent-messages">
            {messages.map((message, index) => (
              <div className={`agent-message ${message.role}`} key={`${message.role}-${index}`}>
                {message.text}
              </div>
            ))}
            {busy && <div className="agent-message agent">처리 중...</div>}
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
            />
            <button className="button primary" type="submit" disabled={busy || !text.trim()}>
              <Send size={16} />
              보내기
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
        <Bot size={24} />
      </button>
    </div>
  );
}
