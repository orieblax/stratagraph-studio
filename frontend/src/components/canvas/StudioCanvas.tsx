'use client';

import React, { useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  NodeTypes,
  EdgeTypes,
} from '@xyflow/react';
import CustomAgentNode from './CustomAgentNode';
import CustomMCPNode from './CustomMCPNode';
import AnimatedPulseEdge from './AnimatedPulseEdge';
import { useTopologyStore } from '@/store/useTopologyStore';
import { Database, Loader2 } from 'lucide-react';

export default function StudioCanvas() {
  const nodes = useTopologyStore((s) => s.nodes);
  const edges = useTopologyStore((s) => s.edges);
  const onNodesChange = useTopologyStore((s) => s.onNodesChange);
  const onEdgesChange = useTopologyStore((s) => s.onEdgesChange);
  const warehouseWarmupMessage = useTopologyStore((s) => s.warehouseWarmupMessage);

  const nodeTypes: NodeTypes = useMemo(
    () => ({
      agentNode: CustomAgentNode,
      mcpNode: CustomMCPNode,
    }),
    []
  );

  const edgeTypes: EdgeTypes = useMemo(
    () => ({
      animatedPulse: AnimatedPulseEdge,
    }),
    []
  );

  return (
    <div className="w-full h-full relative overflow-hidden bg-slate-950">
      {/* Databricks Warehouse Warmup Toast / Banner */}
      {warehouseWarmupMessage && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-4 py-2 rounded-lg bg-indigo-950/90 border border-indigo-700/80 shadow-[0_0_20px_rgba(99,102,241,0.4)] text-indigo-200 text-xs backdrop-blur-md animate-pulse">
          <Database className="w-4 h-4 text-indigo-400 animate-spin" />
          <span>{warehouseWarmupMessage}</span>
          <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-300" />
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e293b" />
        <Controls position="bottom-right" showInteractive={false} />
        <MiniMap
          position="bottom-left"
          nodeStrokeWidth={3}
          nodeColor={(node) => {
            if (node.id === 'mcp_tool_execution_node') return '#f59e0b';
            if (node.data?.status === 'running') return '#06b6d4';
            if (node.data?.status === 'success') return '#10b981';
            if (node.data?.status === 'cache_hit') return '#2dd4bf';
            if (node.data?.status === 'hitl_paused') return '#f59e0b';
            return '#334155';
          }}
          maskColor="rgba(3, 7, 18, 0.75)"
        />
      </ReactFlow>
    </div>
  );
}
