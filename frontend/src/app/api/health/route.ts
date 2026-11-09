import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({
    status: 'ok',
    service: 'stratagraph-studio-frontend',
    deployment_target: 'vercel',
    timestamp: new Date().toISOString(),
    backend_configured: Boolean(
      process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL
    ),
  });
}
