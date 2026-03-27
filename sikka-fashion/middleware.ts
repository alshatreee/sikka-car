// Middleware disabled for demo mode
// Re-enable Clerk middleware when auth keys are configured

import { NextResponse } from "next/server";

export function middleware() {
  return NextResponse.next();
}

export const config = {
  matcher: [],
};
