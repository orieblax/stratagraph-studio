/**
 * Core TypeScript definitions for StrataGraph Studio Visual Canvas & Control Plane
 */

export type NodeExecutionStatus =
  | 'idle'
  | 'running'
  | 'success'
  | 'cache_hit'
  | 'error'
  | 'tainted_locked'
  | 'hitl_paused';

export type AgentNodeData = {
  label: string;
  category: 'guardrail' | 'cache' | 'router' | 'etl' | 'retrieval' | 'rerank' | 'synthesis' | 'eval';
  status: NodeExecutionStatus;
  executionTimeMs?: number;
  microCostUsd?: number;
  tokenCount?: number;
  tainted?: boolean;
  activeRoute?: string;
  details?: Record<string, unknown>;
  onSelect?: () => void;
};

export type MCPNodeData = {
  serverName: string;
  toolName: string;
  transport: 'stdio' | 'sse';
  status: NodeExecutionStatus;
  label?: string;
  executionTimeMs?: number;
  microCostUsd?: number;
  tokenCount?: number;
  sqlAstVerified?: boolean;
  tainted?: boolean;
  argumentsPreview?: Record<string, unknown>;
  details?: Record<string, unknown>;
  onSelect?: () => void;
};

export type TopologyEvent = {
  event_type:
    | 'node_start'
    | 'node_end'
    | 'edge_active'
    | 'mcp_call'
    | 'hitl_interrupt'
    | 'warehouse_warmup'
    | 'eval_score';
  node_id: string;
  status: string;
  execution_time_ms?: number;
  micro_cost_usd?: number;
  token_count?: number;
  tainted?: boolean;
  correlation_id: string;
  timestamp?: number;
  details?: Record<string, unknown>;
};

export type TokenStreamEvent = {
  channel: 'token_stream_event';
  delta: string;
  accumulated_length: number;
  is_complete: boolean;
  correlation_id: string;
  timestamp?: number;
};

export type CheckpointSnapshot = {
  checkpoint_id: string;
  created_at: string;
  next_nodes: string[];
  values: Record<string, unknown>;
};

export type StudioConfig = {
  llmProvider: 'openai' | 'anthropic' | 'ollama' | 'databricks';
  modelName: string;
  temperature: number;
  smartTieringEnabled: boolean;
  maxIterations: number;
  maxCostUsd: number;
  vectorBackend: 'postgres_local' | 'supabase_cloud' | 'databricks_vector_search';
  databricksVolumePath: string;
  databricksWarehouseHttpPath: string;
  semanticCacheEnabled: boolean;
  semanticCacheThreshold: number;
  chunkSize: number;
  chunkOverlap: number;
  rerankerDevicePolicy: 'onnx-int8' | 'cpu' | 'cuda';
  rerankerScoreCutoff: number;
  langsmithSamplingRate: number;
  spotlightingEnabled: boolean;
  manualHitlTools: string[];
  // Ephemeral credentials (passed in headers only)
  openaiApiKey: string;
  anthropicApiKey: string;
  databricksToken: string;
  supabaseServiceKey: string;
};
