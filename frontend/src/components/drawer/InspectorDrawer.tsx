'use client';

import React from 'react';
import {
  X,
  FileText,
  Search,
  Shield,
  BarChart,
  Copy,
  Check,
  Terminal,
  Database,
  Flame,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { useConfigStore } from '@/store/useConfigStore';
import { useTopologyStore } from '@/store/useTopologyStore';
import { useTokenStreamStore } from '@/store/useTokenStreamStore';

export default function InspectorDrawer() {
  const isInspectorDrawerOpen = useConfigStore((s) => s.isInspectorDrawerOpen);
  const setInspectorDrawerOpen = useConfigStore((s) => s.setInspectorDrawerOpen);
  const activeTab = useConfigStore((s) => s.activeInspectorTab);
  const setActiveTab = useConfigStore((s) => s.setActiveInspectorTab);

  const selectedNodeId = useTopologyStore((s) => s.selectedNodeId);
  const nodes = useTopologyStore((s) => s.nodes);
  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  const markdownBuffer = useTokenStreamStore((s) => s.markdownBuffer);
  const isStreaming = useTokenStreamStore((s) => s.isStreaming);
  const totalTokens = useTokenStreamStore((s) => s.totalTokensAccumulated);
  const totalCost = useTokenStreamStore((s) => s.totalCostUsd);
  const evalScores = useTokenStreamStore((s) => s.evalScores);
  const sqlAuditLogs = useTokenStreamStore((s) => s.sqlAuditLogs);

  const [copied, setCopied] = React.useState(false);

  if (!isInspectorDrawerOpen) return null;

  const handleCopyMarkdown = () => {
    navigator.clipboard.writeText(markdownBuffer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] z-40 bg-slate-900/95 backdrop-blur-xl border-l border-slate-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase tracking-wider text-cyan-400">Node Inspector</span>
            {selectedNode && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-medium">
                {('label' in selectedNode.data ? selectedNode.data.label : selectedNode.data.toolName) || selectedNode.id}
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-0.5">Execution Telemetry, RAG Comparison & Audit Logs</p>
        </div>
        <button
          onClick={() => setInspectorDrawerOpen(false)}
          className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* 4 Tabs Bar */}
      <div className="grid grid-cols-4 border-b border-slate-800 text-xs font-medium text-slate-400">
        <button
          onClick={() => setActiveTab('state_diff')}
          className={`py-2.5 flex items-center justify-center gap-1 border-b-2 transition ${
            activeTab === 'state_diff'
              ? 'border-cyan-400 text-cyan-300 bg-slate-800/40'
              : 'border-transparent hover:text-slate-300'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          State Diff
        </button>
        <button
          onClick={() => setActiveTab('rag_rerank')}
          className={`py-2.5 flex items-center justify-center gap-1 border-b-2 transition ${
            activeTab === 'rag_rerank'
              ? 'border-cyan-400 text-cyan-300 bg-slate-800/40'
              : 'border-transparent hover:text-slate-300'
          }`}
        >
          <Search className="w-3.5 h-3.5" />
          RAG/Rerank
        </button>
        <button
          onClick={() => setActiveTab('mcp_security')}
          className={`py-2.5 flex items-center justify-center gap-1 border-b-2 transition ${
            activeTab === 'mcp_security'
              ? 'border-cyan-400 text-cyan-300 bg-slate-800/40'
              : 'border-transparent hover:text-slate-300'
          }`}
        >
          <Shield className="w-3.5 h-3.5" />
          MCP Audit
        </button>
        <button
          onClick={() => setActiveTab('finops_evals')}
          className={`py-2.5 flex items-center justify-center gap-1 border-b-2 transition ${
            activeTab === 'finops_evals'
              ? 'border-cyan-400 text-cyan-300 bg-slate-800/40'
              : 'border-transparent hover:text-slate-300'
          }`}
        >
          <BarChart className="w-3.5 h-3.5" />
          FinOps/Eval
        </button>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs text-slate-300">
        {/* TAB 1: STATE DIFF */}
        {activeTab === 'state_diff' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-slate-400 text-[11px]">
              <span>Active Node State Payload</span>
              <span className="font-mono text-cyan-400">{selectedNodeId || 'root_workflow'}</span>
            </div>
            <pre className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[11px] text-cyan-300 overflow-x-auto max-h-[300px]">
              {JSON.stringify(selectedNode?.data || { message: 'Select a canvas node to inspect state diff' }, null, 2)}
            </pre>
          </div>
        )}

        {/* TAB 2: RAG & RE-RANK VISUALIZER */}
        {activeTab === 'rag_rerank' && (
          <div className="space-y-3">
            <div className="text-[11px] text-slate-400">
              Candidate Chunks Comparison: Vector Cosine + BM25 RRF vs. Quantized Cross-Encoder
            </div>

            <div className="space-y-2">
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                <div className="flex items-center justify-between font-mono text-[11px]">
                  <span className="text-cyan-300 font-semibold">chunk_delta_lake_01</span>
                  <div className="flex gap-2">
                    <span className="text-slate-400">Vector: 0.92</span>
                    <span className="text-indigo-400">BM25: 1.45</span>
                    <span className="text-emerald-400 font-bold">Rerank: 0.9699 (PASS)</span>
                  </div>
                </div>
                <p className="text-[11px] text-slate-300 font-mono bg-slate-900/60 p-2 rounded border border-slate-800">
                  &lt;untrusted_context_e4b8a1&gt;
                  Databricks Lakehouse Vector Search integrates directly with Delta Lake tables using automated Delta Sync pipelines.
                  &lt;/untrusted_context_e4b8a1&gt;
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                <div className="flex items-center justify-between font-mono text-[11px]">
                  <span className="text-cyan-300 font-semibold">chunk_delta_lake_02</span>
                  <div className="flex gap-2">
                    <span className="text-slate-400">Vector: 0.88</span>
                    <span className="text-indigo-400">BM25: 1.10</span>
                    <span className="text-emerald-400 font-bold">Rerank: 0.8312 (PASS)</span>
                  </div>
                </div>
                <p className="text-[11px] text-slate-300 font-mono bg-slate-900/60 p-2 rounded border border-slate-800">
                  &lt;untrusted_context_a9f2c3&gt;
                  Unity Catalog governs access to Delta tables, MLflow models, and Vector Search indexes with centralized RBAC.
                  &lt;/untrusted_context_a9f2c3&gt;
                </p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: MCP & SECURITY AUDIT */}
        {activeTab === 'mcp_security' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-slate-400 text-[11px]">
              <span>SQL Security AST Log (sqlglot)</span>
              <span className="text-emerald-400 font-mono">Defense-in-Depth Active</span>
            </div>

            <div className="space-y-2">
              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[11px] space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">SELECT id, title FROM bronze_docs LIMIT 10</span>
                  <span className="text-emerald-400 text-[10px]">ALLOWED</span>
                </div>
                <div className="text-[10px] text-slate-500">AST Check: No DDL, LIMIT 100 clamped, Table Allowlisted</div>
              </div>

              {sqlAuditLogs.map((log, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[11px] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300">{log.query}</span>
                    <span className={log.allowed ? 'text-emerald-400' : 'text-rose-400'}>
                      {log.allowed ? 'ALLOWED' : 'BLOCKED'}
                    </span>
                  </div>
                  {log.reason && <div className="text-[10px] text-rose-400">{log.reason}</div>}
                </div>
              ))}
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1 text-[11px]">
              <div className="text-slate-200 font-medium">PII & Secret Redaction Policy</div>
              <p className="text-slate-400">
                Automatic regex masking enabled for API keys, bearer tokens, emails, phone numbers, and SSNs across all logged payloads and checkpoints.
              </p>
            </div>
          </div>
        )}

        {/* TAB 4: FINOPS & EVALS */}
        {activeTab === 'finops_evals' && (
          <div className="space-y-4">
            {/* Cost & Tokens Card */}
            <div className="grid grid-cols-2 gap-2">
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-400 text-[10px] uppercase tracking-wider block">Accumulated Cost</span>
                <span className="text-lg font-bold font-mono text-emerald-400">
                  ${totalCost > 0 ? totalCost.toFixed(5) : '0.00000'}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">FinOps Micro-Cost</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                <span className="text-slate-400 text-[10px] uppercase tracking-wider block">Total Tokens</span>
                <span className="text-lg font-bold font-mono text-cyan-400">{totalTokens} tok</span>
                <span className="text-[10px] text-slate-500 block mt-0.5">Prompt + Completion</span>
              </div>
            </div>

            {/* LangSmith Evaluators Scorecard */}
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200">LangSmith LLM-as-a-Judge RAG Triad</span>
                <span className="text-[10px] font-mono text-cyan-400">Run ID: ls_run_01</span>
              </div>

              <div className="space-y-2 text-[11px]">
                <div>
                  <div className="flex justify-between mb-0.5">
                    <span className="text-slate-400">Context Relevance</span>
                    <span className="font-mono text-emerald-400">
                      {(evalScores.context_relevance ?? 0.88).toFixed(2)} / 1.00
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{ width: `${(evalScores.context_relevance ?? 0.88) * 100}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between mb-0.5">
                    <span className="text-slate-400">Groundedness (Faithfulness)</span>
                    <span className="font-mono text-emerald-400">
                      {(evalScores.groundedness ?? 0.95).toFixed(2)} / 1.00
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{ width: `${(evalScores.groundedness ?? 0.95) * 100}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between mb-0.5">
                    <span className="text-slate-400">Answer Relevance</span>
                    <span className="font-mono text-emerald-400">
                      {(evalScores.answer_relevance ?? 0.92).toFixed(2)} / 1.00
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{ width: `${(evalScores.answer_relevance ?? 0.92) * 100}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between mb-0.5">
                    <span className="text-slate-400">Trajectory Efficiency Score</span>
                    <span className="font-mono text-cyan-400">
                      {(evalScores.trajectory_score ?? 0.90).toFixed(2)} / 1.00
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-cyan-500 rounded-full"
                      style={{ width: `${(evalScores.trajectory_score ?? 0.90) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Real-time Streaming Output Drawer */}
      <div className="h-56 border-t border-slate-800 bg-slate-950 p-4 flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-semibold text-slate-200">Synthesis Output Stream</span>
            {isStreaming && (
              <span className="flex items-center gap-1 text-[10px] text-cyan-400 font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                50ms Throttled Buffer
              </span>
            )}
          </div>
          <button
            onClick={handleCopyMarkdown}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition text-[11px] flex items-center gap-1"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto font-sans text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-3 rounded-lg border border-slate-800 whitespace-pre-wrap select-text">
          {markdownBuffer || (
            <span className="text-slate-500 italic">Synthesized LLM output will stream here in real time...</span>
          )}
        </div>
      </div>
    </div>
  );
}
