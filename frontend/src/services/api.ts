import { StudioConfig, TopologyEvent, TokenStreamEvent } from '@/types';

export function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_BACKEND_URL) {
    return process.env.NEXT_PUBLIC_BACKEND_URL.replace(/\/+$/, '');
  }
  if (typeof window !== 'undefined') {
    // In production browser, route via Next.js proxy to avoid CORS
    return '/api/backend';
  }
  return (process.env.BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
}

function getEphemeralHeaders(config: StudioConfig): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: 'Bearer developer-admin-token',
  };

  if (config.openaiApiKey) headers['X-OpenAI-Key'] = config.openaiApiKey;
  if (config.anthropicApiKey) headers['X-Anthropic-Key'] = config.anthropicApiKey;
  if (config.databricksToken) headers['X-Databricks-Token'] = config.databricksToken;
  if (config.supabaseServiceKey) headers['X-Supabase-Key'] = config.supabaseServiceKey;

  return headers;
}

export async function executeWorkflow(
  payload: Record<string, unknown>,
  config: StudioConfig,
  onTopologyEvent?: (evt: TopologyEvent) => void,
  onTokenStreamEvent?: (evt: TokenStreamEvent) => void
): Promise<any> {
  // 1. Start SSE stream reader concurrently
  const threadId = String(payload.thread_id || 'default_thread');
  let eventSource: EventSource | null = null;

  if (typeof window !== 'undefined') {
    try {
      const sseUrl = `${getApiBase()}/api/v1/orchestration/stream/${threadId}`;
      eventSource = new EventSource(sseUrl);

      eventSource.addEventListener('topology_event', (e) => {
        try {
          const data = JSON.parse(e.data);
          onTopologyEvent?.(data);
        } catch {}
      });

      eventSource.addEventListener('token_stream_event', (e) => {
        try {
          const data = JSON.parse(e.data);
          onTokenStreamEvent?.(data);
        } catch {}
      });
    } catch (err) {
      console.warn('SSE stream connection warning:', err);
    }
  }

  try {
    const res = await fetch(`${getApiBase()}/api/v1/orchestration/run`, {
      method: 'POST',
      headers: getEphemeralHeaders(config),
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Execution error HTTP ${res.status}: ${await res.text()}`);
    }

    const finalState = await res.json();
    return finalState;
  } finally {
    if (eventSource) {
      setTimeout(() => eventSource.close(), 1000);
    }
  }
}

export async function resumeWorkflow(
  payload: { thread_id: string; approved: boolean; modification?: Record<string, unknown> },
  config: StudioConfig,
  onTopologyEvent?: (evt: TopologyEvent) => void,
  onTokenStreamEvent?: (evt: TokenStreamEvent) => void
): Promise<any> {
  const res = await fetch(`${getApiBase()}/api/v1/orchestration/resume`, {
    method: 'POST',
    headers: getEphemeralHeaders(config),
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Resume error HTTP ${res.status}: ${await res.text()}`);
  }

  return await res.json();
}

export async function forkCheckpoint(
  payload: { thread_id: string; checkpoint_id: string; new_thread_id: string },
  config: StudioConfig
): Promise<any> {
  const res = await fetch(`${getApiBase()}/api/v1/orchestration/fork`, {
    method: 'POST',
    headers: getEphemeralHeaders(config),
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Fork error HTTP ${res.status}: ${await res.text()}`);
  }

  return await res.json();
}

export async function fetchCheckpoints(threadId: string, config: StudioConfig): Promise<any[]> {
  const res = await fetch(`${getApiBase()}/api/v1/orchestration/checkpoints/${threadId}`, {
    method: 'GET',
    headers: getEphemeralHeaders(config),
  });

  if (!res.ok) {
    return [];
  }

  const data = await res.json();
  return data.checkpoints || [];
}
