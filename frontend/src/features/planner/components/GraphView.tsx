import { AlertTriangle, ArrowLeft, CheckCircle2, GitBranch } from "lucide-react";
import {
  langGraphColumns,
  langGraphEdges,
  langGraphNodes,
  langGraphStats,
  type LangGraphNodeInfo,
} from "../data/langGraphFlow";

interface GraphViewProps {
  onBack: () => void;
}

const nodeById = new Map(langGraphNodes.map((node) => [node.id, node]));

function nodeClassName(node: LangGraphNodeInfo) {
  return `graph-node ${node.kind}`;
}

function outgoingLabels(nodeId: string) {
  return langGraphEdges
    .filter((edge) => edge.from === nodeId && edge.label)
    .map((edge) => edge.label)
    .join(" / ");
}

export function GraphView({ onBack }: GraphViewProps) {
  const stats = langGraphStats();
  const conditionalEdges = langGraphEdges.filter((edge) => edge.conditional);

  return (
    <main className="view graph-view">
      <div className="graph-toolbar">
        <div>
          <span>LangGraph</span>
          <h2>일정 배치 그래프</h2>
          <p>입력 해석부터 검증, 배치, 사용자 승인까지의 실행 흐름입니다.</p>
        </div>
        <button className="button ghost" type="button" onClick={onBack}>
          <ArrowLeft size={16} />
          돌아가기
        </button>
      </div>

      <section className="graph-stats" aria-label="LangGraph 요약">
        <div>
          <strong>{stats.nodeCount}</strong>
          <span>노드</span>
        </div>
        <div>
          <strong>{stats.edgeCount}</strong>
          <span>엣지</span>
        </div>
        <div>
          <strong>{stats.conditionalGateCount}</strong>
          <span>조건 분기</span>
        </div>
        <div>
          <strong>{stats.exitPathCount}</strong>
          <span>종료 경로</span>
        </div>
      </section>

      <section className="graph-board" aria-label="LangGraph 실행 다이어그램">
        {langGraphColumns.map((column) => (
          <div className="graph-column" key={column.title}>
            <div className="graph-column-heading">
              <strong>{column.title}</strong>
              <span>{column.caption}</span>
            </div>
            <div className="graph-node-stack">
              {column.nodeIds.map((nodeId, index) => {
                const node = nodeById.get(nodeId);
                if (!node) return null;
                return (
                  <div className="graph-node-wrap" key={node.id}>
                    {index > 0 && <span className="graph-connector" aria-hidden="true" />}
                    <article className={nodeClassName(node)}>
                      <span>{node.kind}</span>
                      <strong>{node.label}</strong>
                      <p>{node.detail}</p>
                      {outgoingLabels(node.id) && (
                        <em>
                          <GitBranch size={13} />
                          {outgoingLabels(node.id)}
                        </em>
                      )}
                    </article>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </section>

      <section className="graph-branches" aria-label="조건 분기 상세">
        <div className="graph-section-title">
          <GitBranch size={17} />
          <h3>조건 분기</h3>
        </div>
        <div className="graph-branch-list">
          {conditionalEdges.map((edge) => (
            <div className="graph-branch-row" key={`${edge.from}-${edge.to}-${edge.label}`}>
              <span>{nodeById.get(edge.from)?.label}</span>
              <strong>{edge.label}</strong>
              <span>{nodeById.get(edge.to)?.label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="graph-notes" aria-label="실행 의미">
        <div>
          <CheckCircle2 size={18} />
          <strong>승인 경로</strong>
          <p>
            사용자가 제안을 승인하면 <code>finalize_node</code>가 최종 일정을 확정합니다.
          </p>
        </div>
        <div>
          <AlertTriangle size={18} />
          <strong>재배치 경로</strong>
          <p>
            거절되면 <code>interpret_rejection_node</code>가 피드백을 해석하고 다음 재계획 입력으로
            남깁니다.
          </p>
        </div>
      </section>
    </main>
  );
}
