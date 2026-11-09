'use client';

import React from 'react';
import StudioCanvas from '@/components/canvas/StudioCanvas';
import ConfigPanel from '@/components/panels/ConfigPanel';
import InspectorDrawer from '@/components/drawer/InspectorDrawer';
import ExecutionBar from '@/components/controls/ExecutionBar';
import { useTopologyStore } from '@/store/useTopologyStore';
import { useConfigStore } from '@/store/useConfigStore';
import {
  Layers,
  Activity,
  Sliders,
  PanelRight,
  Database,
  Cpu,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react';

export default function StudioPage() {
  const activeThreadId = useTopologyStore((s) => s.activeThreadId);
  const isExecuting = useTopologyStore((s) => s.isExecuting);
  const toggleConfigPanel = useConfigStore((s) => s.toggleConfigPanel);
  const setInspectorDrawerOpen = useConfigStore((s) => s.setInspectorDrawerOpen);
  const config = useConfigStore((s) => s.config);

  return (
    <main className="relative w-screen h-screen bg-slate-950 overflow-hidden flex flex-col select-none">
      {/* Top Navigation Header */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-5 flex items-center justify-between z-20 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-600 shadow-md shadow-cyan-950 flex items-center justify-center">
            <Layers className="w-5 h-5 text-slate-950 font-bold" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-tight text-slate-100 font-sans">StrataGraph Studio</h1>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">
                v0.1.0
              </span>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center gap-2">
              <span>LangGraph Cyclic Multi-Agent Orchestration & Medallion RAG</span>
            </div>
          </div>
        </div>

        {/* System Status Indicators Strip */}
        <div className="hidden lg:flex items-center gap-3 text-xs font-mono">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-950 border border-slate-800 text-slate-300">
            <span className={`w-2 h-2 rounded-full ${isExecuting ? 'bg-cyan-400 animate-ping' : 'bg-emerald-400'}`} />
            <span>FastAPI Monolith</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-950 border border-slate-800 text-slate-300">
            <Database className="w-3.5 h-3.5 text-indigo-400" />
            <span className="capitalize">{config.vectorBackend.replace('_', ' ')}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-950 border border-slate-800 text-slate-300">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span>{config.rerankerDevicePolicy}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-950 border border-slate-800 text-slate-300">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>sqlglot AST</span>
          </div>
        </div>

        {/* Top Right Quick Actions */}
        <div className="flex items-center gap-2">
          <div className="text-xs font-mono text-slate-400 hidden sm:block bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
            Thread: <span className="text-cyan-400">{activeThreadId.slice(0, 16)}...</span>
          </div>

          <button
            onClick={toggleConfigPanel}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 border border-slate-700/60 transition flex items-center gap-1.5 text-xs font-medium"
          >
            <Sliders className="w-4 h-4 text-cyan-400" />
            <span className="hidden sm:inline">Settings</span>
          </button>

          <button
            onClick={() => setInspectorDrawerOpen(true)}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 border border-slate-700/60 transition flex items-center gap-1.5 text-xs font-medium"
          >
            <PanelRight className="w-4 h-4 text-cyan-400" />
            <span className="hidden sm:inline">Inspector</span>
          </button>
        </div>
      </header>

      {/* Main Interactive Flow Canvas */}
      <div className="flex-1 w-full h-full relative">
        <StudioCanvas />
      </div>

      {/* Floating Bottom Execution Control Bar */}
      <ExecutionBar />

      {/* Sliding Modals / Panels */}
      <ConfigPanel />
      <InspectorDrawer />
    </main>
  );
}
