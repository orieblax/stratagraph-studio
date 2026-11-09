import { describe, it, expect, beforeEach } from 'vitest';
import { useTopologyStore } from '@/store/useTopologyStore';
import { useTokenStreamStore } from '@/store/useTokenStreamStore';
import { useConfigStore } from '@/store/useConfigStore';
import { TopologyEvent, TokenStreamEvent } from '@/types';

describe('Frontend Zustand Stores — Decoupled Dual-Channel Architecture', () => {
  beforeEach(() => {
    useTopologyStore.getState().resetCanvas();
    useTokenStreamStore.getState().clearStream();
  });

  it('useTopologyStore initializes 9 LangGraph nodes and pulses edges upon event', () => {
    const store = useTopologyStore.getState();
    expect(store.nodes.length).toBe(9);
    expect(store.edges.length).toBe(12);

    // Apply node start event
    const startEvt: TopologyEvent = {
      event_type: 'node_start',
      node_id: 'input_guardrail_node',
      status: 'Running',
      correlation_id: 'cid_123',
    };
    store.applyTopologyEvent(startEvt);

    const updatedNode = useTopologyStore.getState().nodes.find((n) => n.id === 'input_guardrail_node');
    expect(updatedNode?.data.status).toBe('running');

    // Connecting edge should be animated and active
    const connectingEdge = useTopologyStore.getState().edges.find((e) => e.source === 'input_guardrail_node');
    expect(connectingEdge?.animated).toBe(true);
    expect(connectingEdge?.data?.active).toBe(true);

    // Apply node end event
    const endEvt: TopologyEvent = {
      event_type: 'node_end',
      node_id: 'input_guardrail_node',
      status: 'Success',
      execution_time_ms: 24.5,
      micro_cost_usd: 0.0001,
      correlation_id: 'cid_123',
    };
    store.applyTopologyEvent(endEvt);

    const doneNode = useTopologyStore.getState().nodes.find((n) => n.id === 'input_guardrail_node');
    expect(doneNode?.data.status).toBe('success');
    expect(doneNode?.data.executionTimeMs).toBe(24.5);
    expect(doneNode?.data.microCostUsd).toBe(0.0001);
  });

  it('useTopologyStore handles HITL interrupts with pending action payload', () => {
    const store = useTopologyStore.getState();
    const hitlEvt: TopologyEvent = {
      event_type: 'hitl_interrupt',
      node_id: 'mcp_tool_execution_node',
      status: 'Waiting for Operator Review',
      correlation_id: 'cid_hitl_001',
      details: {
        server_name: 'workspace-ops-mcp',
        tool_name: 'send_email',
        arguments: { recipient: 'ops@acme.corp' },
      },
    };

    store.applyTopologyEvent(hitlEvt);

    const state = useTopologyStore.getState();
    expect(state.hitlPendingAction).not.toBeNull();
    expect(state.hitlPendingAction?.tool_name).toBe('send_email');
    expect(state.isExecuting).toBe(false);

    const mcpNode = state.nodes.find((n) => n.id === 'mcp_tool_execution_node');
    expect(mcpNode?.data.status).toBe('hitl_paused');
  });

  it('useTokenStreamStore buffers throttled tokens without mutating topology canvas store', () => {
    const streamStore = useTokenStreamStore.getState();
    const topoStoreBefore = useTopologyStore.getState().nodes;

    const deltaEvt1: TokenStreamEvent = {
      channel: 'token_stream_event',
      delta: 'Databricks ',
      accumulated_length: 11,
      is_complete: false,
      correlation_id: 'cid_stream_01',
    };
    streamStore.appendTokenDelta(deltaEvt1);

    const deltaEvt2: TokenStreamEvent = {
      channel: 'token_stream_event',
      delta: 'Delta Lake ACID guarantees.',
      accumulated_length: 38,
      is_complete: true,
      correlation_id: 'cid_stream_01',
    };
    streamStore.appendTokenDelta(deltaEvt2);

    const streamState = useTokenStreamStore.getState();
    expect(streamState.markdownBuffer).toBe('Databricks Delta Lake ACID guarantees.');
    expect(streamState.isStreaming).toBe(false);

    // Topology canvas store should not be affected by token streaming
    const topoStoreAfter = useTopologyStore.getState().nodes;
    expect(topoStoreAfter.length).toBe(topoStoreBefore.length);
  });

  it('useConfigStore updates config and toggles drawer panels correctly', () => {
    const configStore = useConfigStore.getState();

    configStore.updateConfig({
      llmProvider: 'databricks',
      vectorBackend: 'databricks_vector_search',
      maxCostUsd: 3.50,
    });

    const updated = useConfigStore.getState().config;
    expect(updated.llmProvider).toBe('databricks');
    expect(updated.vectorBackend).toBe('databricks_vector_search');
    expect(updated.maxCostUsd).toBe(3.50);

    // Toggle Config Panel
    configStore.toggleConfigPanel();
    expect(useConfigStore.getState().isConfigPanelOpen).toBe(true);

    // Open Inspector Drawer and switch tabs
    configStore.setActiveInspectorTab('rag_rerank');
    expect(useConfigStore.getState().isInspectorDrawerOpen).toBe(true);
    expect(useConfigStore.getState().activeInspectorTab).toBe('rag_rerank');
  });
});
