import { create } from 'zustand';
import { Node, Edge, applyNodeChanges, applyEdgeChanges, NodeChange, EdgeChange } from '@xyflow/react';
import { AgentNodeData, MCPNodeData, TopologyEvent, CheckpointSnapshot } from '@/types';

// Default initial DAG node positions for the 9-node LangGraph cyclic workflow
const INITIAL_NODES: Node<AgentNodeData | MCPNodeData>[] = [
  {
    id: 'input_guardrail_node',
    type: 'agentNode',
    position: { x: 50, y: 180 },
    data: {
      label: '1. Input Guardrail',
      category: 'guardrail',
      status: 'idle',
      details: { description: 'PII Scrubber & Prompt Injection AST Scanner' },
    },
  },
  {
    id: 'semantic_cache_memory_node',
    type: 'agentNode',
    position: { x: 380, y: 180 },
    data: {
      label: '2. Semantic Cache',
      category: 'cache',
      status: 'idle',
      details: { description: 'Tier-1 Exact SHA-256 & Tier-2 pgvector Cosine' },
    },
  },
  {
    id: 'supervisor_router_node',
    type: 'agentNode',
    position: { x: 720, y: 180 },
    data: {
      label: '3. Supervisor Router',
      category: 'router',
      status: 'idle',
      details: { description: 'Intent Classifier & FinOps Circuit Breaker' },
    },
  },
  {
    id: 'etl_medallion_embedding_node',
    type: 'agentNode',
    position: { x: 520, y: 380 },
    data: {
      label: '4. Medallion ETL',
      category: 'etl',
      status: 'idle',
      details: { description: 'Outbox Chunker & Delta Sync Upsert' },
    },
  },
  {
    id: 'hybrid_retriever_node',
    type: 'agentNode',
    position: { x: 720, y: 380 },
    data: {
      label: '5. Hybrid Retriever',
      category: 'retrieval',
      status: 'idle',
      details: { description: 'Vector + BM25 RRF Search & XML Spotlighting' },
    },
  },
  {
    id: 'reranker_node',
    type: 'agentNode',
    position: { x: 720, y: 580 },
    data: {
      label: '6. Quantized Re-Ranker',
      category: 'rerank',
      status: 'idle',
      details: { description: 'ONNX-INT8 Cross-Encoder Scoring (VRAM Protected)' },
    },
  },
  {
    id: 'mcp_tool_execution_node',
    type: 'mcpNode',
    position: { x: 1040, y: 380 },
    data: {
      serverName: 'mcp-hub',
      toolName: 'Dynamic Tool / HITL Gate',
      transport: 'stdio',
      status: 'idle',
      sqlAstVerified: true,
      details: { description: 'Zero-Trust Sandboxed Execution & HITL Approval' },
    },
  },
  {
    id: 'synthesis_output_guardrail_node',
    type: 'agentNode',
    position: { x: 1100, y: 180 },
    data: {
      label: '8. Synthesis Guardrail',
      category: 'synthesis',
      status: 'idle',
      details: { description: 'LLM Generation, Leak Scrubbing & Cache Population' },
    },
  },
  {
    id: 'async_langsmith_eval_node',
    type: 'agentNode',
    position: { x: 1450, y: 180 },
    data: {
      label: '9. LangSmith Evals',
      category: 'eval',
      status: 'idle',
      details: { description: 'Off-Critical-Path RAG Triad & Trajectory Judge' },
    },
  },
];

const INITIAL_EDGES: Edge[] = [
  { id: 'e_guardrail_cache', source: 'input_guardrail_node', target: 'semantic_cache_memory_node', type: 'animatedPulse' },
  { id: 'e_cache_router', source: 'semantic_cache_memory_node', target: 'supervisor_router_node', type: 'animatedPulse' },
  { id: 'e_cache_synthesis', source: 'semantic_cache_memory_node', target: 'synthesis_output_guardrail_node', type: 'animatedPulse' },
  { id: 'e_router_etl', source: 'supervisor_router_node', target: 'etl_medallion_embedding_node', type: 'animatedPulse' },
  { id: 'e_router_retrieval', source: 'supervisor_router_node', target: 'hybrid_retriever_node', type: 'animatedPulse' },
  { id: 'e_router_mcp', source: 'supervisor_router_node', target: 'mcp_tool_execution_node', type: 'animatedPulse' },
  { id: 'e_router_synthesis', source: 'supervisor_router_node', target: 'synthesis_output_guardrail_node', type: 'animatedPulse' },
  { id: 'e_etl_router', source: 'etl_medallion_embedding_node', target: 'supervisor_router_node', type: 'animatedPulse' },
  { id: 'e_retrieval_rerank', source: 'hybrid_retriever_node', target: 'reranker_node', type: 'animatedPulse' },
  { id: 'e_rerank_router', source: 'reranker_node', target: 'supervisor_router_node', type: 'animatedPulse' },
  { id: 'e_mcp_router', source: 'mcp_tool_execution_node', target: 'supervisor_router_node', type: 'animatedPulse' },
  { id: 'e_synthesis_eval', source: 'synthesis_output_guardrail_node', target: 'async_langsmith_eval_node', type: 'animatedPulse' },
];

interface TopologyState {
  nodes: Node<AgentNodeData | MCPNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  activeCorrelationId: string | null;
  activeThreadId: string;
  isExecuting: boolean;
  hitlPendingAction: Record<string, unknown> | null;
  checkpoints: CheckpointSnapshot[];
  warehouseWarmupMessage: string | null;

  // Actions
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  setSelectedNodeId: (id: string | null) => void;
  setActiveThreadId: (threadId: string) => void;
  setIsExecuting: (executing: boolean) => void;
  setHitlPendingAction: (action: Record<string, unknown> | null) => void;
  setCheckpoints: (checkpoints: CheckpointSnapshot[]) => void;
  applyTopologyEvent: (event: TopologyEvent) => void;
  resetCanvas: () => void;
}

export const useTopologyStore = create<TopologyState>((set, get) => ({
  nodes: INITIAL_NODES,
  edges: INITIAL_EDGES,
  selectedNodeId: null,
  activeCorrelationId: null,
  activeThreadId: `thread_${Date.now()}`,
  isExecuting: false,
  hitlPendingAction: null,
  checkpoints: [],
  warehouseWarmupMessage: null,

  onNodesChange: (changes) => {
    set({ nodes: applyNodeChanges(changes, get().nodes) as Node<AgentNodeData | MCPNodeData>[] });
  },

  onEdgesChange: (changes) => {
    set({ edges: applyEdgeChanges(changes, get().edges) });
  },

  setSelectedNodeId: (id) => set({ selectedNodeId: id }),

  setActiveThreadId: (threadId) => set({ activeThreadId: threadId }),

  setIsExecuting: (executing) => set({ isExecuting: executing }),

  setHitlPendingAction: (action) => set({ hitlPendingAction: action }),

  setCheckpoints: (checkpoints) => set({ checkpoints }),

  applyTopologyEvent: (event) => {
    const { event_type, node_id, status, execution_time_ms, micro_cost_usd, token_count, tainted, correlation_id, details } = event;

    // 1. Warehouse warmup telemetry toast
    if (event_type === 'warehouse_warmup') {
      set({ warehouseWarmupMessage: status });
      return;
    }

    // 2. HITL Interrupt handling
    if (event_type === 'hitl_interrupt') {
      set({
        hitlPendingAction: details || { reason: status },
        isExecuting: false,
      });
    }

    // 3. Update target Node visual attributes
    set((state) => {
      const updatedNodes = state.nodes.map((node) => {
        if (node.id === node_id) {
          const currentData = node.data;
          let nodeStatus: AgentNodeData['status'] = 'idle';

          if (event_type === 'node_start') nodeStatus = 'running';
          else if (event_type === 'hitl_interrupt') nodeStatus = 'hitl_paused';
          else if (status.toLowerCase().includes('cache hit')) nodeStatus = 'cache_hit';
          else if (status.toLowerCase().includes('blocked') || tainted) nodeStatus = 'tainted_locked';
          else if (event_type === 'node_end') nodeStatus = status === 'Error' ? 'error' : 'success';

          return {
            ...node,
            data: {
              ...currentData,
              status: nodeStatus,
              executionTimeMs: execution_time_ms ?? currentData.executionTimeMs,
              microCostUsd: micro_cost_usd ?? currentData.microCostUsd,
              tokenCount: token_count ?? currentData.tokenCount,
              tainted: tainted ?? currentData.tainted,
              details: details ? { ...currentData.details, ...details } : currentData.details,
            },
          };
        }
        return node;
      });

      // 4. Update active connecting Edges with glow pulse
      const updatedEdges = state.edges.map((edge) => {
        if (edge.source === node_id && event_type === 'node_start') {
          return { ...edge, animated: true, data: { active: true } };
        }
        if (edge.source === node_id && event_type === 'node_end') {
          return { ...edge, animated: false, data: { active: false } };
        }
        return edge;
      });

      return {
        nodes: updatedNodes,
        edges: updatedEdges,
        activeCorrelationId: correlation_id || state.activeCorrelationId,
        warehouseWarmupMessage: event_type === 'node_end' ? null : state.warehouseWarmupMessage,
      };
    });
  },

  resetCanvas: () => {
    set({
      nodes: INITIAL_NODES.map((n) => ({
        ...n,
        data: { ...n.data, status: 'idle', executionTimeMs: undefined, microCostUsd: undefined, tokenCount: undefined },
      })),
      edges: INITIAL_EDGES.map((e) => ({ ...e, animated: false, data: { active: false } })),
      hitlPendingAction: null,
      warehouseWarmupMessage: null,
      isExecuting: false,
    });
  },
}));
