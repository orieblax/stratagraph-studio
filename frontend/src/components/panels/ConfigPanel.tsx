'use client';

import React, { useState } from 'react';
import {
  X,
  Sliders,
  Database,
  Cpu,
  ShieldCheck,
  Flame,
  Check,
  AlertTriangle,
  Lock,
  Sparkles,
} from 'lucide-react';
import { useConfigStore } from '@/store/useConfigStore';

export default function ConfigPanel() {
  const isConfigPanelOpen = useConfigStore((s) => s.isConfigPanelOpen);
  const toggleConfigPanel = useConfigStore((s) => s.toggleConfigPanel);
  const config = useConfigStore((s) => s.config);
  const updateConfig = useConfigStore((s) => s.updateConfig);

  const [activeTab, setActiveTab] = useState<'llm_finops' | 'databricks' | 'rag_vram' | 'security'>('llm_finops');

  if (!isConfigPanelOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-96 z-40 bg-slate-900/95 backdrop-blur-xl border-l border-slate-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
      {/* Panel Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Sliders className="w-5 h-5 text-cyan-400" />
          <h2 className="text-sm font-semibold text-slate-100">Studio Configuration</h2>
        </div>
        <button
          onClick={toggleConfigPanel}
          className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* 4 Tabs Bar */}
      <div className="grid grid-cols-4 border-b border-slate-800 text-xs font-medium text-slate-400">
        <button
          onClick={() => setActiveTab('llm_finops')}
          className={`py-2.5 flex items-center justify-center gap-1 border-b-2 transition ${
            activeTab === 'llm_finops'
              ? 'border-cyan-400 text-cyan-300 bg-slate-800/40'
              : 'border-transparent hover:text-slate-300'
          }`}
        >
          <Flame className="w-3.5 h-3.5" />
          FinOps
        </button>
        <button
          onClick={() => setActiveTab('databricks')}
          className={`py-2.5 flex items-center justify-center gap-1 border-b-2 transition ${
            activeTab === 'databricks'
              ? 'border-cyan-400 text-cyan-300 bg-slate-800/40'
              : 'border-transparent hover:text-slate-300'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          Lakehouse
        </button>
        <button
          onClick={() => setActiveTab('rag_vram')}
          className={`py-2.5 flex items-center justify-center gap-1 border-b-2 transition ${
            activeTab === 'rag_vram'
              ? 'border-cyan-400 text-cyan-300 bg-slate-800/40'
              : 'border-transparent hover:text-slate-300'
          }`}
        >
          <Cpu className="w-3.5 h-3.5" />
          RAG/VRAM
        </button>
        <button
          onClick={() => setActiveTab('security')}
          className={`py-2.5 flex items-center justify-center gap-1 border-b-2 transition ${
            activeTab === 'security'
              ? 'border-cyan-400 text-cyan-300 bg-slate-800/40'
              : 'border-transparent hover:text-slate-300'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          Security
        </button>
      </div>

      {/* Tab Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs text-slate-300">
        {/* TAB 1: LLM & FINOPS */}
        {activeTab === 'llm_finops' && (
          <div className="space-y-4">
            <div>
              <label className="block text-slate-400 mb-1 font-medium">LLM Provider</label>
              <select
                value={config.llmProvider}
                onChange={(e) => updateConfig({ llmProvider: e.target.value as any })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="openai">OpenAI (Direct Cloud)</option>
                <option value="anthropic">Anthropic Claude</option>
                <option value="ollama">Ollama (Host Machine Local)</option>
                <option value="databricks">Databricks Model Serving</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-medium">Model Name</label>
              <input
                type="text"
                value={config.modelName}
                onChange={(e) => updateConfig({ modelName: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <label className="text-slate-400 font-medium">Temperature</label>
                <span className="font-mono text-cyan-400">{config.temperature}</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={config.temperature}
                onChange={(e) => updateConfig({ temperature: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-200">Smart Model Tiering</span>
                <input
                  type="checkbox"
                  checked={config.smartTieringEnabled}
                  onChange={(e) => updateConfig({ smartTieringEnabled: e.target.checked })}
                  className="rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-0"
                />
              </div>
              <p className="text-[11px] text-slate-400">
                Routes lightweight tasks (Guardrails, Intent Routing) to small models or local Ollama, reserving heavy models for final synthesis.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 space-y-3">
              <div className="text-slate-200 font-medium flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                FinOps Circuit Breakers
              </div>
              <div>
                <div className="flex justify-between mb-1 text-[11px]">
                  <span className="text-slate-400">Max Iterations (Loop Limit)</span>
                  <span className="font-mono text-cyan-400">{config.maxIterations} loops</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={config.maxIterations}
                  onChange={(e) => updateConfig({ maxIterations: parseInt(e.target.value) })}
                  className="w-full accent-cyan-400"
                />
              </div>
              <div>
                <div className="flex justify-between mb-1 text-[11px]">
                  <span className="text-slate-400">Max Workflow Cost (USD)</span>
                  <span className="font-mono text-emerald-400">${config.maxCostUsd.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.10"
                  max="5.00"
                  step="0.10"
                  value={config.maxCostUsd}
                  onChange={(e) => updateConfig({ maxCostUsd: parseFloat(e.target.value) })}
                  className="w-full accent-emerald-400"
                />
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: DATABRICKS & LAKEHOUSE */}
        {activeTab === 'databricks' && (
          <div className="space-y-4">
            <div>
              <label className="block text-slate-400 mb-1 font-medium">Vector Store Backend</label>
              <select
                value={config.vectorBackend}
                onChange={(e) => updateConfig({ vectorBackend: e.target.value as any })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="postgres_local">Local PostgreSQL (pgvector HNSW + BM25 RRF)</option>
                <option value="supabase_cloud">Supabase Cloud (pgvector)</option>
                <option value="databricks_vector_search">Databricks Lakehouse Vector Search</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-medium">Unity Catalog Medallion Volume Path</label>
              <input
                type="text"
                value={config.databricksVolumePath}
                onChange={(e) => updateConfig({ databricksVolumePath: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-cyan-500"
              />
              <span className="text-[10px] text-slate-500">Unity Catalog Volume for Bronze raw document landing.</span>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-medium">Databricks SQL Warehouse HTTP Path</label>
              <input
                type="text"
                value={config.databricksWarehouseHttpPath}
                onChange={(e) => updateConfig({ databricksWarehouseHttpPath: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800/80">
              <div className="text-slate-300 font-medium mb-1">Cold-Start Manager</div>
              <p className="text-[11px] text-slate-400">
                Automatically detects Databricks SQL Warehouse cold-start warming states and emits visual status notifications to the canvas node during wake-up.
              </p>
            </div>
          </div>
        )}

        {/* TAB 3: RAG & HARDWARE VRAM */}
        {activeTab === 'rag_vram' && (
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-indigo-950/40 border border-indigo-800/50">
              <div className="flex items-center gap-1.5 font-medium text-indigo-300 mb-1">
                <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                VRAM Protection Architecture
              </div>
              <p className="text-[11px] text-indigo-200/80">
                Quantized ONNX-INT8 Re-Ranker runs on CPU to guarantee dedicated local GPU VRAM for Ollama LLM execution.
              </p>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-medium">Re-Ranker Device Policy</label>
              <select
                value={config.rerankerDevicePolicy}
                onChange={(e) => updateConfig({ rerankerDevicePolicy: e.target.value as any })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="onnx-int8">onnx-int8 (CPU Quantized — VRAM Safe)</option>
                <option value="cpu">cpu (Standard FP32)</option>
                <option value="cuda">cuda (GPU Accelerated)</option>
              </select>
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <label className="text-slate-400 font-medium">Re-Ranker Score Cutoff</label>
                <span className="font-mono text-cyan-400">{config.rerankerScoreCutoff}</span>
              </div>
              <input
                type="range"
                min="0.10"
                max="0.90"
                step="0.05"
                value={config.rerankerScoreCutoff}
                onChange={(e) => updateConfig({ rerankerScoreCutoff: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <label className="text-slate-400 font-medium">Chunk Size (chars)</label>
                <span className="font-mono text-cyan-400">{config.chunkSize}</span>
              </div>
              <input
                type="range"
                min="200"
                max="1500"
                step="50"
                value={config.chunkSize}
                onChange={(e) => updateConfig({ chunkSize: parseInt(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <label className="text-slate-400 font-medium">Chunk Overlap (chars)</label>
                <span className="font-mono text-cyan-400">{config.chunkOverlap}</span>
              </div>
              <input
                type="range"
                min="20"
                max="300"
                step="10"
                value={config.chunkOverlap}
                onChange={(e) => updateConfig({ chunkOverlap: parseInt(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>
          </div>
        )}

        {/* TAB 4: SECURITY & EVALS */}
        {activeTab === 'security' && (
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-200">Two-Tier Semantic Cache</span>
                <input
                  type="checkbox"
                  checked={config.semanticCacheEnabled}
                  onChange={(e) => updateConfig({ semanticCacheEnabled: e.target.checked })}
                  className="rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-0"
                />
              </div>
              <div className="flex justify-between text-[11px] pt-1">
                <span className="text-slate-400">Cosine Threshold</span>
                <span className="font-mono text-cyan-400">{config.semanticCacheThreshold}</span>
              </div>
              <input
                type="range"
                min="0.80"
                max="0.99"
                step="0.01"
                value={config.semanticCacheThreshold}
                onChange={(e) => updateConfig({ semanticCacheThreshold: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-200">Cryptographic XML Spotlighting</span>
                <input
                  type="checkbox"
                  checked={config.spotlightingEnabled}
                  onChange={(e) => updateConfig({ spotlightingEnabled: e.target.checked })}
                  className="rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-0"
                />
              </div>
              <p className="text-[11px] text-slate-400">
                Wraps external retrieved chunks in &lt;untrusted_context_nonce&gt; tags to neutralize indirect prompt injection attempts.
              </p>
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <label className="text-slate-400 font-medium">LangSmith Eval Sampling Rate</label>
                <span className="font-mono text-cyan-400">{Math.round(config.langsmithSamplingRate * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={config.langsmithSamplingRate}
                onChange={(e) => updateConfig({ langsmithSamplingRate: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>

            {/* Ephemeral Secrets Header Injection */}
            <div className="p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 space-y-3">
              <div className="flex items-center gap-1.5 text-rose-300 font-medium">
                <Lock className="w-3.5 h-3.5 text-rose-400" />
                Ephemeral Secrets Vault
              </div>
              <p className="text-[10px] text-rose-200/70">
                Passed exclusively via ephemeral request headers (SecretStr). Never saved to PostgreSQL checkpoints or LangSmith traces.
              </p>

              <div>
                <label className="block text-slate-400 text-[10px] mb-1">OPENAI_API_KEY</label>
                <input
                  type="password"
                  placeholder="sk-proj-..."
                  value={config.openaiApiKey}
                  onChange={(e) => updateConfig({ openaiApiKey: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-1.5 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-rose-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 text-[10px] mb-1">DATABRICKS_TOKEN</label>
                <input
                  type="password"
                  placeholder="dapi..."
                  value={config.databricksToken}
                  onChange={(e) => updateConfig({ databricksToken: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-1.5 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-rose-500"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
