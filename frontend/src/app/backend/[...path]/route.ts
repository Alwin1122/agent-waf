import { NextRequest, NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const baseUrl = (process.env.BACKEND_API_URL ?? DEFAULT_BACKEND_URL).replace(
    /\/$/,
    "",
  );
  const backendPath = path.map(encodeURIComponent).join("/");
  const target = new URL(`${baseUrl}/${backendPath}`);
  target.search = request.nextUrl.search;

  try {
    const response = await fetch(target, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    return new NextResponse(await response.arrayBuffer(), {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("Content-Type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      {
        status: "error",
        message: "The Agent WAF backend is unavailable.",
      },
      { status: 502 },
    );
  }
}
