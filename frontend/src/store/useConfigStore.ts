import { create } from 'zustand';
import { StudioConfig } from '@/types';

interface ConfigState {
  config: StudioConfig;
  isConfigPanelOpen: boolean;
  isInspectorDrawerOpen: boolean;
  activeInspectorTab: 'state_diff' | 'rag_rerank' | 'mcp_security' | 'finops_evals';

  // Actions
  updateConfig: (partial: Partial<StudioConfig>) => void;
  toggleConfigPanel: () => void;
  setInspectorDrawerOpen: (open: boolean) => void;
  setActiveInspectorTab: (tab: 'state_diff' | 'rag_rerank' | 'mcp_security' | 'finops_evals') => void;
}

export const useConfigStore = create<ConfigState>((set) => ({
  config: {
    llmProvider: 'openai',
    modelName: 'gpt-4o',
    temperature: 0.7,
    smartTieringEnabled: true,
    maxIterations: 3,
    maxCostUsd: 1.5,
    vectorBackend: 'postgres_local',
    databricksVolumePath: '/Volumes/prod_catalog/bronze_raw/files/',
    databricksWarehouseHttpPath: '/sql/1.0/warehouses/a1b2c3d4e5f6',
    semanticCacheEnabled: true,
    semanticCacheThreshold: 0.92,
    chunkSize: 500,
    chunkOverlap: 50,
    rerankerDevicePolicy: 'onnx-int8',
    rerankerScoreCutoff: 0.35,
    langsmithSamplingRate: 0.25,
    spotlightingEnabled: true,
    manualHitlTools: ['send_email', 'execute_local_write_query', 'create_task'],
    openaiApiKey: '',
    anthropicApiKey: '',
    databricksToken: '',
    supabaseServiceKey: '',
  },
  isConfigPanelOpen: false,
  isInspectorDrawerOpen: false,
  activeInspectorTab: 'finops_evals',

  updateConfig: (partial) =>
    set((state) => ({ config: { ...state.config, ...partial } })),

  toggleConfigPanel: () =>
    set((state) => ({ isConfigPanelOpen: !state.isConfigPanelOpen })),

  setInspectorDrawerOpen: (open) =>
    set({ isInspectorDrawerOpen: open }),

  setActiveInspectorTab: (tab) =>
    set({ activeInspectorTab: tab, isInspectorDrawerOpen: true }),
}));
