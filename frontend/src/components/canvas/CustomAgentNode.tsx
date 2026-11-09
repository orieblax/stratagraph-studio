import React from 'react';
import { Handle, Position, Node, NodeProps } from '@xyflow/react';
import {
  Shield,
  Database,
  GitFork,
  Search,
  Sliders,
  Brain,
  BarChart2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  DollarSign,
  Layers,
  Sparkles,
} from 'lucide-react';
import { AgentNodeData } from '@/types';
import { useConfigStore } from '@/store/useConfigStore';
import { useTopologyStore } from '@/store/useTopologyStore';

export default function CustomAgentNode(props: NodeProps) {
  const id = props.id;
  const data = props.data as unknown as AgentNodeData;
  const setSelectedNodeId = useTopologyStore((s) => s.setSelectedNodeId);
  const setInspectorDrawerOpen = useConfigStore((s) => s.setInspectorDrawerOpen);
  const setActiveInspectorTab = useConfigStore((s) => s.setActiveInspectorTab);

  const getCategoryIcon = (category: AgentNodeData['category']) => {
    switch (category) {
      case 'guardrail':
        return <Shield className="w-4 h-4 text-emerald-400" />;
      case 'cache':
        return <Database className="w-4 h-4 text-cyan-400" />;
      case 'router':
        return <GitFork className="w-4 h-4 text-indigo-400" />;
      case 'etl':
        return <Layers className="w-4 h-4 text-amber-400" />;
      case 'retrieval':
        return <Search className="w-4 h-4 text-blue-400" />;
      case 'rerank':
        return <Sliders className="w-4 h-4 text-purple-400" />;
      case 'synthesis':
        return <Brain className="w-4 h-4 text-teal-400" />;
      case 'eval':
        return <BarChart2 className="w-4 h-4 text-rose-400" />;
      default:
        return <Sparkles className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusStyle = (status: AgentNodeData['status']) => {
    switch (status) {
      case 'running':
        return 'border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.35)] animate-pulse';
      case 'success':
        return 'border-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.2)]';
      case 'cache_hit':
        return 'border-teal-400 shadow-[0_0_12px_rgba(45,212,191,0.3)] ring-1 ring-teal-400';
      case 'tainted_locked':
        return 'border-rose-500 shadow-[0_0_12px_rgba(244,63,94,0.3)] bg-rose-950/20';
      case 'hitl_paused':
        return 'border-amber-400 shadow-[0_0_15px_rgba(251,191,36,0.4)] animate-bounce';
      case 'error':
        return 'border-red-600 shadow-[0_0_10px_rgba(220,38,38,0.3)]';
      case 'idle':
      default:
        return 'border-slate-800 hover:border-slate-700';
    }
  };

  const getStatusBadge = (status: AgentNodeData['status']) => {
    switch (status) {
      case 'running':
        return (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-300 border border-cyan-800">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
            Executing
          </span>
        );
      case 'success':
        return (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-800">
            <CheckCircle2 className="w-2.5 h-2.5" />
            Done
          </span>
        );
      case 'cache_hit':
        return (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-teal-950/80 text-teal-300 border border-teal-700">
            <Database className="w-2.5 h-2.5" />
            Tier-1 Hit ($0.00)
          </span>
        );
      case 'tainted_locked':
        return (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-rose-950/80 text-rose-300 border border-rose-800">
            <AlertTriangle className="w-2.5 h-2.5" />
            Spotlighted / Tainted
          </span>
        );
      case 'hitl_paused':
        return (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-amber-950/80 text-amber-300 border border-amber-700">
            <Clock className="w-2.5 h-2.5" />
            HITL Review Gate
          </span>
        );
      case 'error':
        return (
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-red-950/80 text-red-300 border border-red-800">
            Failed
          </span>
        );
      default:
        return (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-900 text-slate-400 border border-slate-800">
            Idle
          </span>
        );
    }
  };

  const handleNodeClick = () => {
    setSelectedNodeId(id);
    if (data.category === 'retrieval' || data.category === 'rerank') {
      setActiveInspectorTab('rag_rerank');
    } else if (data.category === 'eval') {
      setActiveInspectorTab('finops_evals');
    } else {
      setActiveInspectorTab('state_diff');
    }
    setInspectorDrawerOpen(true);
  };

  return (
    <div
      onClick={handleNodeClick}
      className={`w-64 rounded-xl border bg-slate-900/90 backdrop-blur-md p-3.5 transition-all duration-200 cursor-pointer ${getStatusStyle(
        data.status
      )}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-700 !w-2.5 !h-2.5" />

      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-slate-800/80 border border-slate-700/50">
            {getCategoryIcon(data.category)}
          </div>
          <span className="text-xs font-semibold text-slate-200">{data.label}</span>
        </div>
        {getStatusBadge(data.status)}
      </div>

      {/* Description / Subtitle */}
      {Boolean(data.details?.description) && (
        <p className="text-[11px] text-slate-400 line-clamp-1 mb-2">
          {String(data.details?.description)}
        </p>
      )}

      {/* Real-time Telemetry Metrics Strip */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[10px] text-slate-400 font-mono">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3 text-slate-500" />
          <span>{data.executionTimeMs !== undefined ? `${data.executionTimeMs}ms` : '—'}</span>
        </div>

        <div className="flex items-center gap-1">
          <DollarSign className="w-3 h-3 text-emerald-500" />
          <span>{data.microCostUsd !== undefined ? `$${data.microCostUsd.toFixed(4)}` : '$0.00'}</span>
        </div>

        {data.tokenCount !== undefined && (
          <div className="text-slate-400">
            <span>{data.tokenCount} tok</span>
          </div>
        )}
      </div>

      {/* Cryptographic Spotlighting Tainted Badge */}
      {data.tainted && (
        <div className="mt-2 py-0.5 px-1.5 rounded bg-rose-950/60 border border-rose-800/60 flex items-center gap-1 text-[9px] text-rose-300 font-mono">
          <AlertTriangle className="w-2.5 h-2.5 shrink-0" />
          <span className="truncate">&lt;untrusted_context_nonce&gt;</span>
        </div>
      )}

      <Handle type="source" position={Position.Right} className="!bg-slate-700 !w-2.5 !h-2.5" />
    </div>
  );
}
