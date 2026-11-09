import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

function getBackendBaseUrl(): string {
  return (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    'http://127.0.0.1:8000'
  ).replace(/\/+$/, '');
}

async function proxyRequest(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const backendBase = getBackendBaseUrl();
  const searchParams = req.nextUrl.search;
  
  // Normalize path if caller included api/v1
  let cleanPath = path.join('/');
  if (cleanPath.startsWith('api/v1/')) {
    cleanPath = cleanPath.substring(7);
  } else if (cleanPath.startsWith('api/')) {
    cleanPath = cleanPath.substring(4);
  }
  
  const targetUrl = `${backendBase}/api/v1/${cleanPath}${searchParams}`;

  // Forward request headers
  const forwardHeaders = new Headers();
  req.headers.forEach((value, key) => {
    const lowerKey = key.toLowerCase();
    // Exclude hop-by-hop headers
    if (!['host', 'connection', 'keep-alive', 'transfer-encoding'].includes(lowerKey)) {
      forwardHeaders.set(key, value);
    }
  });

  const method = req.method;
  let body: BodyInit | null = null;
  if (method !== 'GET' && method !== 'HEAD') {
    body = await req.arrayBuffer();
  }

  try {
    const response = await fetch(targetUrl, {
      method,
      headers: forwardHeaders,
      body,
      // @ts-expect-error duplex required for streaming in Node fetch
      duplex: 'half',
      cache: 'no-store',
    });

    const isSSE = response.headers.get('content-type')?.includes('text/event-stream');

    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      const lowerKey = key.toLowerCase();
      if (!['transfer-encoding', 'connection'].includes(lowerKey)) {
        responseHeaders.set(key, value);
      }
    });

    if (isSSE) {
      responseHeaders.set('Cache-Control', 'no-cache, no-transform');
      responseHeaders.set('Connection', 'keep-alive');
      responseHeaders.set('Content-Type', 'text/event-stream');
    }

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error: any) {
    console.error(`[Vercel Backend Proxy] Failed to proxy to ${targetUrl}:`, error);
    return NextResponse.json(
      {
        error: 'Failed to communicate with StrataGraph backend service',
        target: targetUrl,
        message: error?.message || String(error),
      },
      { status: 502 }
    );
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, ctx);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, ctx);
}

export async function PUT(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, ctx);
}

export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, ctx);
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-OpenAI-Key, X-Anthropic-Key, X-Databricks-Token, X-Supabase-Key',
    },
  });
}
