import React from 'react';
import { describe, it, expect } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import CustomAgentNode from '@/components/canvas/CustomAgentNode';
import CustomMCPNode from '@/components/canvas/CustomMCPNode';
import ConfigPanel from '@/components/panels/ConfigPanel';
import InspectorDrawer from '@/components/drawer/InspectorDrawer';
import { useConfigStore } from '@/store/useConfigStore';
import { useTokenStreamStore } from '@/store/useTokenStreamStore';
import { useTopologyStore } from '@/store/useTopologyStore';

// Wrapper to provide React Flow context mock
function renderWithFlow(ui: React.ReactElement) {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
}

describe('Frontend Visual UI Components', () => {
  it('CustomAgentNode renders category label, execution time, and status badge', () => {
    const mockProps: any = {
      id: 'input_guardrail_node',
      data: {
        label: '1. Input Guardrail',
        category: 'guardrail',
        status: 'success',
        executionTimeMs: 14.8,
        microCostUsd: 0.0002,
        tokenCount: 42,
        details: { description: 'PII Scrubber and AST Guard' },
      },
    };

    renderWithFlow(<CustomAgentNode {...mockProps} />);

    expect(screen.getByText('1. Input Guardrail')).toBeInTheDocument();
    expect(screen.getByText('14.8ms')).toBeInTheDocument();
    expect(screen.getByText('$0.0002')).toBeInTheDocument();
    expect(screen.getByText('42 tok')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
  });

  it('CustomAgentNode renders cryptographic XML spotlighting badge when tainted', () => {
    const mockProps: any = {
      id: 'hybrid_retriever_node',
      data: {
        label: '5. Hybrid Retriever',
        category: 'retrieval',
        status: 'tainted_locked',
        tainted: true,
      },
    };

    renderWithFlow(<CustomAgentNode {...mockProps} />);
    expect(screen.getByText('<untrusted_context_nonce>')).toBeInTheDocument();
  });

  it('CustomMCPNode renders server name, tool name, and AST verification badge', () => {
    const mockProps: any = {
      id: 'mcp_tool_execution_node',
      data: {
        serverName: 'postgres-local-mcp',
        toolName: 'execute_local_read_query',
        transport: 'stdio',
        status: 'idle',
        sqlAstVerified: true,
      },
    };

    renderWithFlow(<CustomMCPNode {...mockProps} />);
    expect(screen.getByText('7. MCP Tool Node')).toBeInTheDocument();
    expect(screen.getByText('postgres-local-mcp')).toBeInTheDocument();
    expect(screen.getByText('execute_local_read_query')).toBeInTheDocument();
    expect(screen.getByText('stdio [sandboxed]')).toBeInTheDocument();
    expect(screen.getByText('sqlglot AST OK')).toBeInTheDocument();
  });

  it('ConfigPanel switches across all 4 configuration tabs', () => {
    useConfigStore.setState({ isConfigPanelOpen: true });
    render(<ConfigPanel />);

    expect(screen.getByText('Studio Configuration')).toBeInTheDocument();

    // Tab 1: FinOps
    expect(screen.getByText('Smart Model Tiering')).toBeInTheDocument();

    // Tab 2: Lakehouse
    fireEvent.click(screen.getByText('Lakehouse'));
    expect(screen.getByText('Unity Catalog Medallion Volume Path')).toBeInTheDocument();

    // Tab 3: RAG/VRAM
    fireEvent.click(screen.getByText('RAG/VRAM'));
    expect(screen.getByText('VRAM Protection Architecture')).toBeInTheDocument();

    // Tab 4: Security
    fireEvent.click(screen.getByText('Security'));
    expect(screen.getByText('Ephemeral Secrets Vault')).toBeInTheDocument();
  });

  it('InspectorDrawer renders streaming markdown output and evaluators scorecard', () => {
    useConfigStore.setState({ isInspectorDrawerOpen: true, activeInspectorTab: 'finops_evals' });
    useTokenStreamStore.setState({
      markdownBuffer: '### Medallion Architecture Summary\nGold table contains verified embeddings.',
      totalCostUsd: 0.00142,
      totalTokensAccumulated: 240,
      evalScores: {
        context_relevance: 0.94,
        groundedness: 0.98,
        answer_relevance: 0.96,
        trajectory_score: 0.95,
      },
    });

    render(<InspectorDrawer />);

    expect(screen.getByText('Synthesis Output Stream')).toBeInTheDocument();
    expect(screen.getByText(/Medallion Architecture Summary/)).toBeInTheDocument();
    expect(screen.getByText('LangSmith LLM-as-a-Judge RAG Triad')).toBeInTheDocument();
    expect(screen.getByText('$0.00142')).toBeInTheDocument();
    expect(screen.getByText('240 tok')).toBeInTheDocument();
  });
});
