import type { Metadata } from 'next';
import './globals.css';
import '@xyflow/react/dist/style.css';

export const metadata: Metadata = {
  title: 'StrataGraph Studio — Visual Agentic Orchestration & Medallion RAG',
  description: 'Enterprise Visual Multi-Agent LangGraph Control Plane with MCP and Databricks Lakehouse Integration',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-slate-950 text-slate-100 min-h-screen w-screen overflow-hidden">
        {children}
      </body>
    </html>
  );
}
