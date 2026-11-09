'use client';

import React, { useState } from 'react';
import {
  Play,
  RotateCcw,
  Sliders,
  PanelRight,
  ShieldAlert,
  CheckCircle,
  XCircle,
  GitBranch,
  Loader2,
  Send,
} from 'lucide-react';
import { useTopologyStore } from '@/store/useTopologyStore';
import { useConfigStore } from '@/store/useConfigStore';
import { useTokenStreamStore } from '@/store/useTokenStreamStore';
import { executeWorkflow, resumeWorkflow, forkCheckpoint } from '@/services/api';

const PRESET_QUERIES = [
  'Explain ACID in Delta Lake',
  'Incorporate marketing doc into Medallion pipeline',
  'Please send email to ops-lead regarding status',
];

export default function ExecutionBar() {
  const [query, setQuery] = useState('How does Databricks Lakehouse Vector Search integrate with Delta tables?');

  const isExecuting = useTopologyStore((s) => s.isExecuting);
  const setIsExecuting = useTopologyStore((s) => s.setIsExecuting);
  const activeThreadId = useTopologyStore((s) => s.activeThreadId);
  const setActiveThreadId = useTopologyStore((s) => s.setActiveThreadId);
  const hitlPendingAction = useTopologyStore((s) => s.hitlPendingAction);
  const setHitlPendingAction = useTopologyStore((s) => s.setHitlPendingAction);
  const resetCanvas = useTopologyStore((s) => s.resetCanvas);
  const applyTopologyEvent = useTopologyStore((s) => s.applyTopologyEvent);
  const checkpoints = useTopologyStore((s) => s.checkpoints);
  const setCheckpoints = useTopologyStore((s) => s.setCheckpoints);

  const toggleConfigPanel = useConfigStore((s) => s.toggleConfigPanel);
  const setInspectorDrawerOpen = useConfigStore((s) => s.setInspectorDrawerOpen);
  const config = useConfigStore((s) => s.config);

  const clearStream = useTokenStreamStore((s) => s.clearStream);
  const appendTokenDelta = useTokenStreamStore((s) => s.appendTokenDelta);
  const setAccumulatedCost = useTokenStreamStore((s) => s.setAccumulatedCost);
  const setEvalScores = useTokenStreamStore((s) => s.setEvalScores);

  const handleRun = async () => {
    if (!query.trim() || isExecuting) return;

    resetCanvas();
    clearStream();
    setIsExecuting(true);

    try {
      const response = await executeWorkflow(
        {
          user_query: query,
          thread_id: activeThreadId,
          provider: config.llmProvider,
          model: config.modelName,
          temperature: config.temperature,
          vector_backend: config.vectorBackend,
          semantic_cache_enabled: config.semanticCacheEnabled,
          semantic_cache_threshold: config.semanticCacheThreshold,
          max_iterations: config.maxIterations,
          max_cost_usd: config.maxCostUsd,
          reranker_device_policy: config.rerankerDevicePolicy,
          eval_sampling_rate: config.langsmithSamplingRate,
          manual_hitl_tools: config.manualHitlTools,
        },
        config,
        // On topology event callback
        (topoEvt) => {
          applyTopologyEvent(topoEvt);
        },
        // On token stream callback
        (tokEvt) => {
          appendTokenDelta(tokEvt);
        }
      );

      if (response?.accumulated_cost_usd !== undefined) {
        setAccumulatedCost(response.accumulated_cost_usd);
      }
      if (response?.eval_scores) {
        setEvalScores(response.eval_scores);
      }

      if (response?.hitl_pending_action) {
        setHitlPendingAction(response.hitl_pending_action);
      }
    } catch (err) {
      console.error('Workflow execution error:', err);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleHitlDecision = async (approved: boolean) => {
    if (!hitlPendingAction) return;

    setIsExecuting(true);
    try {
      const response = await resumeWorkflow(
        {
          thread_id: activeThreadId,
          approved,
        },
        config,
        (topoEvt) => applyTopologyEvent(topoEvt),
        (tokEvt) => appendTokenDelta(tokEvt)
      );

      setHitlPendingAction(null);
      if (response?.accumulated_cost_usd !== undefined) {
        setAccumulatedCost(response.accumulated_cost_usd);
      }
      if (response?.eval_scores) {
        setEvalScores(response.eval_scores);
      }
    } catch (err) {
      console.error('HITL Resume error:', err);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleForkCheckpoint = async (checkpointId: string) => {
    const newThread = `fork_${Date.now()}`;
    try {
      await forkCheckpoint(
        {
          thread_id: activeThreadId,
          checkpoint_id: checkpointId,
          new_thread_id: newThread,
        },
        config
      );
      setActiveThreadId(newThread);
      resetCanvas();
    } catch (err) {
      console.error('Fork checkpoint error:', err);
    }
  };

  return (
    <>
      {/* HITL Operator Review Modal Banner */}
      {hitlPendingAction && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 w-[540px] rounded-xl bg-amber-950/95 border-2 border-amber-500 shadow-[0_0_30px_rgba(245,158,11,0.5)] p-4 backdrop-blur-xl animate-in zoom-in-95 duration-200">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-amber-900/80 border border-amber-700">
              <ShieldAlert className="w-5 h-5 text-amber-300" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-bold text-amber-200 flex items-center gap-2">
                Operator Approval Required (HITL Gate)
              </h3>
              <p className="text-xs text-amber-300/80 mt-1">
                {String(hitlPendingAction.reason || 'Mutating tool call detected on tainted execution context.')}
              </p>

              <div className="mt-2.5 p-2 rounded bg-slate-950/90 border border-slate-800 text-[11px] font-mono text-cyan-300 overflow-x-auto max-h-24">
                <div>Tool: {String(hitlPendingAction.tool_name)}</div>
                <div>Server: {String(hitlPendingAction.server_name)}</div>
                <div className="text-slate-400 mt-1">
                  Args: {JSON.stringify(hitlPendingAction.arguments || {})}
                </div>
              </div>

              <div className="mt-3 flex items-center justify-end gap-2">
                <button
                  onClick={() => handleHitlDecision(false)}
                  disabled={isExecuting}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-700 hover:border-rose-700 text-xs font-semibold flex items-center gap-1.5 transition"
                >
                  <XCircle className="w-4 h-4 text-rose-400" />
                  Reject Call
                </button>
                <button
                  onClick={() => handleHitlDecision(true)}
                  disabled={isExecuting}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-emerald-950 transition"
                >
                  {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                  Approve & Execute
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Execution Floating Bar */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 w-full max-w-4xl px-4">
        {/* Preset Queries Pill Bar */}
        <div className="flex items-center gap-2 mb-2 overflow-x-auto pb-1 text-[11px]">
          <span className="text-slate-500 shrink-0">Presets:</span>
          {PRESET_QUERIES.map((preset, idx) => (
            <button
              key={idx}
              onClick={() => setQuery(preset)}
              className="px-2.5 py-1 rounded-full bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-cyan-300 border border-slate-800 transition shrink-0 whitespace-nowrap"
            >
              {preset}
            </button>
          ))}
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/95 backdrop-blur-xl shadow-2xl p-2.5 flex items-center gap-2">
          {/* Query Input */}
          <div className="flex-1 relative flex items-center">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleRun()}
              placeholder="Ask an agent, ingest a Medallion document, or dispatch MCP tools..."
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/80 pr-10 font-sans"
            />
          </div>

          {/* Run Button */}
          <button
            onClick={handleRun}
            disabled={isExecuting || !query.trim()}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-cyan-950 transition disabled:opacity-50"
          >
            {isExecuting ? <Loader2 className="w-4 h-4 animate-spin text-slate-950" /> : <Play className="w-4 h-4 fill-slate-950" />}
            <span>Run Workflow</span>
          </button>

          {/* Reset Canvas Button */}
          <button
            onClick={() => {
              resetCanvas();
              clearStream();
            }}
            title="Reset Canvas"
            className="p-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-slate-100 border border-slate-700/60 transition"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <div className="h-6 w-px bg-slate-800 mx-1" />

          {/* Config Panel Toggle */}
          <button
            onClick={toggleConfigPanel}
            title="Studio Configuration"
            className="p-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-cyan-300 border border-slate-700/60 transition"
          >
            <Sliders className="w-4 h-4" />
          </button>

          {/* Inspector Drawer Toggle */}
          <button
            onClick={() => setInspectorDrawerOpen(true)}
            title="Node Inspector & Telemetry"
            className="p-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-cyan-300 border border-slate-700/60 transition"
          >
            <PanelRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  );
}
