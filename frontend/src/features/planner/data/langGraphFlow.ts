export type LangGraphNodeKind = "system" | "input" | "schedule" | "review" | "exit";

export interface LangGraphNodeInfo {
  id: string;
  label: string;
  detail: string;
  kind: LangGraphNodeKind;
}

export interface LangGraphEdgeInfo {
  from: string;
  to: string;
  label?: string;
  conditional?: boolean;
}

export interface LangGraphColumnInfo {
  title: string;
  caption: string;
  nodeIds: string[];
}

export const langGraphNodes: LangGraphNodeInfo[] = [
  { id: "START", label: "START", detail: "LangGraph 실행 진입점", kind: "system" },
  {
    id: "parse_input_node",
    label: "parse_input",
    detail: "사용자 입력 또는 API payload를 PlannerState로 정규화합니다.",
    kind: "input",
  },
  {
    id: "apply_replan_constraints_node",
    label: "apply_replan_constraints",
    detail: "스누즈, 피드백, 재배치 요청을 작업 제약으로 반영합니다.",
    kind: "input",
  },
  {
    id: "validate_input_node",
    label: "validate_input",
    detail: "필수 정보와 blocking issue를 검사하고 분기 조건을 만듭니다.",
    kind: "input",
  },
  {
    id: "clarification_node",
    label: "clarification",
    detail: "추가 정보가 필요한 경우 질문을 생성하고 실행을 종료합니다.",
    kind: "exit",
  },
  {
    id: "normalize_time_node",
    label: "normalize_time",
    detail: "날짜, 가용 시간, duration 값을 배치 가능한 시간 단위로 맞춥니다.",
    kind: "schedule",
  },
  {
    id: "compute_free_blocks_node",
    label: "compute_free_blocks",
    detail: "고정 일정을 제외한 주간 가용 블록을 계산합니다.",
    kind: "schedule",
  },
  {
    id: "classify_blocks_node",
    label: "classify_blocks",
    detail: "작업 배치에 적합한 시간 블록과 여유 시간을 분류합니다.",
    kind: "schedule",
  },
  {
    id: "rank_tasks_node",
    label: "rank_tasks",
    detail: "우선순위, 기간, 피드백을 기준으로 작업 순서를 정합니다.",
    kind: "schedule",
  },
  {
    id: "place_tasks_node",
    label: "place_tasks",
    detail: "작업을 가능한 시간대에 배치하고 미배치 작업을 기록합니다.",
    kind: "schedule",
  },
  {
    id: "validate_plan_node",
    label: "validate_plan",
    detail: "충돌, buffer 부족, 과도 계획 등 결과 품질을 검증합니다.",
    kind: "review",
  },
  {
    id: "generate_explanation_node",
    label: "generate_explanation",
    detail: "사용자에게 보여줄 배치 이유와 요약을 작성합니다.",
    kind: "review",
  },
  {
    id: "approval_node",
    label: "approval",
    detail: "승인, 거절, 대기 상태를 기준으로 최종 분기를 결정합니다.",
    kind: "review",
  },
  {
    id: "interpret_rejection_node",
    label: "interpret_rejection",
    detail: "거절 사유를 재배치 피드백으로 해석하고 다음 실행을 준비합니다.",
    kind: "exit",
  },
  {
    id: "finalize_node",
    label: "finalize",
    detail: "승인된 draft를 최종 일정으로 확정합니다.",
    kind: "exit",
  },
  { id: "END", label: "END", detail: "LangGraph 실행 종료점", kind: "system" },
];

export const langGraphColumns: LangGraphColumnInfo[] = [
  {
    title: "입력과 검증",
    caption: "사용자 요청을 상태로 만들고 배치 가능 여부를 판단합니다.",
    nodeIds: ["START", "parse_input_node", "apply_replan_constraints_node", "validate_input_node"],
  },
  {
    title: "일정 계산",
    caption: "가용 시간과 작업 우선순위를 계산해 실제 캘린더 블록을 만듭니다.",
    nodeIds: [
      "normalize_time_node",
      "compute_free_blocks_node",
      "classify_blocks_node",
      "rank_tasks_node",
      "place_tasks_node",
    ],
  },
  {
    title: "검증과 설명",
    caption: "생성된 계획의 품질을 검토하고 사용자에게 보여줄 근거를 만듭니다.",
    nodeIds: ["validate_plan_node", "generate_explanation_node", "approval_node"],
  },
  {
    title: "종료 경로",
    caption: "승인, 거절, 대기, 입력 오류가 각각 다른 종료 경로로 이어집니다.",
    nodeIds: ["clarification_node", "interpret_rejection_node", "finalize_node", "END"],
  },
];

export const langGraphEdges: LangGraphEdgeInfo[] = [
  { from: "START", to: "parse_input_node" },
  { from: "parse_input_node", to: "apply_replan_constraints_node" },
  { from: "apply_replan_constraints_node", to: "validate_input_node" },
  { from: "validate_input_node", to: "clarification_node", label: "missing_info", conditional: true },
  { from: "validate_input_node", to: "END", label: "invalid_input", conditional: true },
  { from: "validate_input_node", to: "normalize_time_node", label: "valid", conditional: true },
  { from: "clarification_node", to: "END" },
  { from: "normalize_time_node", to: "compute_free_blocks_node" },
  { from: "compute_free_blocks_node", to: "classify_blocks_node" },
  { from: "classify_blocks_node", to: "rank_tasks_node" },
  { from: "rank_tasks_node", to: "place_tasks_node" },
  { from: "place_tasks_node", to: "validate_plan_node" },
  { from: "validate_plan_node", to: "generate_explanation_node" },
  { from: "generate_explanation_node", to: "approval_node" },
  { from: "approval_node", to: "finalize_node", label: "approved", conditional: true },
  { from: "approval_node", to: "interpret_rejection_node", label: "rejected", conditional: true },
  { from: "approval_node", to: "END", label: "pending | limit", conditional: true },
  { from: "interpret_rejection_node", to: "END" },
  { from: "finalize_node", to: "END" },
];

export function langGraphStats() {
  return {
    nodeCount: langGraphNodes.filter((node) => node.kind !== "system").length,
    edgeCount: langGraphEdges.length,
    conditionalGateCount: 2,
    exitPathCount: langGraphEdges.filter((edge) => edge.to === "END").length,
  };
}
