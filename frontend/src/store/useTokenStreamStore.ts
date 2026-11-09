import { create } from 'zustand';
import { TokenStreamEvent } from '@/types';

interface TokenStreamState {
  markdownBuffer: string;
  isStreaming: boolean;
  totalTokensAccumulated: number;
  totalCostUsd: number;
  evalScores: {
    context_relevance?: number;
    groundedness?: number;
    answer_relevance?: number;
    trajectory_score?: number;
  };
  sqlAuditLogs: Array<{ query: string; allowed: boolean; reason?: string; timestamp: string }>;

  // Actions
  appendTokenDelta: (event: TokenStreamEvent) => void;
  setEvalScores: (scores: Record<string, number>) => void;
  appendSqlAuditLog: (entry: { query: string; allowed: boolean; reason?: string }) => void;
  setAccumulatedCost: (cost: number) => void;
  clearStream: () => void;
}

export const useTokenStreamStore = create<TokenStreamState>((set) => ({
  markdownBuffer: '',
  isStreaming: false,
  totalTokensAccumulated: 0,
  totalCostUsd: 0.0,
  evalScores: {},
  sqlAuditLogs: [],

  appendTokenDelta: (event: TokenStreamEvent) => {
    set((state) => ({
      markdownBuffer: state.markdownBuffer + event.delta,
      isStreaming: !event.is_complete,
      totalTokensAccumulated: Math.max(state.totalTokensAccumulated, Math.round(event.accumulated_length / 4)),
    }));
  },

  setEvalScores: (scores) => set({ evalScores: scores }),

  appendSqlAuditLog: (entry) =>
    set((state) => ({
      sqlAuditLogs: [
        { ...entry, timestamp: new Date().toLocaleTimeString() },
        ...state.sqlAuditLogs.slice(0, 49),
      ],
    })),

  setAccumulatedCost: (cost) => set({ totalCostUsd: cost }),

  clearStream: () =>
    set({
      markdownBuffer: '',
      isStreaming: false,
      totalTokensAccumulated: 0,
      totalCostUsd: 0.0,
      evalScores: {},
    }),
}));
