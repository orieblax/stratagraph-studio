import React from 'react';
import { Handle, Position, Node, NodeProps } from '@xyflow/react';
import { Wrench, Terminal, ShieldCheck, Clock, AlertCircle } from 'lucide-react';
import { MCPNodeData } from '@/types';
import { useConfigStore } from '@/store/useConfigStore';
import { useTopologyStore } from '@/store/useTopologyStore';

export default function CustomMCPNode(props: NodeProps) {
  const id = props.id;
  const data = props.data as unknown as MCPNodeData;
  const setSelectedNodeId = useTopologyStore((s) => s.setSelectedNodeId);
  const setInspectorDrawerOpen = useConfigStore((s) => s.setInspectorDrawerOpen);
  const setActiveInspectorTab = useConfigStore((s) => s.setActiveInspectorTab);

  const handleNodeClick = () => {
    setSelectedNodeId(id);
    setActiveInspectorTab('mcp_security');
    setInspectorDrawerOpen(true);
  };

  const getStatusBorder = () => {
    switch (data.status) {
      case 'running':
        return 'border-amber-400 shadow-[0_0_15px_rgba(251,191,36,0.35)] animate-pulse';
      case 'hitl_paused':
        return 'border-amber-500 shadow-[0_0_18px_rgba(245,158,11,0.5)] animate-bounce ring-2 ring-amber-400';
      case 'success':
        return 'border-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.2)]';
      case 'error':
        return 'border-rose-600 shadow-[0_0_10px_rgba(225,29,72,0.3)]';
      default:
        return 'border-slate-800 hover:border-slate-700';
    }
  };

  return (
    <div
      onClick={handleNodeClick}
      className={`w-68 rounded-xl border bg-slate-900/90 backdrop-blur-md p-3.5 transition-all duration-200 cursor-pointer ${getStatusBorder()}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-700 !w-2.5 !h-2.5" />

      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-amber-950/60 border border-amber-800/40">
            <Wrench className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-200">7. MCP Tool Node</div>
            <div className="text-[10px] text-amber-400 font-mono">{data.serverName}</div>
          </div>
        </div>

        {/* Transport Tag */}
        <span className="flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
          <Terminal className="w-2.5 h-2.5" />
          {data.transport === 'stdio' ? 'stdio [sandboxed]' : 'sse [remote]'}
        </span>
      </div>

      {/* Active Tool Name */}
      <div className="py-1 px-2 mb-2 rounded bg-slate-950/80 border border-slate-800/80 flex items-center justify-between">
        <span className="text-[11px] font-mono text-cyan-300 truncate">{data.toolName}</span>
        {data.status === 'hitl_paused' && (
          <span className="text-[9px] px-1 rounded bg-amber-900/80 text-amber-200 font-semibold uppercase">
            HITL Gate
          </span>
        )}
      </div>

      {/* Security & Telemetry Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[10px] text-slate-400 font-mono">
        <div className="flex items-center gap-1 text-emerald-400">
          <ShieldCheck className="w-3 h-3 text-emerald-400" />
          <span>sqlglot AST OK</span>
        </div>

        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3 text-slate-500" />
          <span>{data.executionTimeMs !== undefined ? `${data.executionTimeMs}ms` : '—'}</span>
        </div>
      </div>

      {/* HITL Pending Notice */}
      {data.status === 'hitl_paused' && (
        <div className="mt-2 py-1 px-2 rounded bg-amber-950/80 border border-amber-700 flex items-center gap-1.5 text-[10px] text-amber-200">
          <AlertCircle className="w-3 h-3 shrink-0 text-amber-400" />
          <span>Requires Operator Approval</span>
        </div>
      )}

      <Handle type="source" position={Position.Right} className="!bg-slate-700 !w-2.5 !h-2.5" />
    </div>
  );
}
