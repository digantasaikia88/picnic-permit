// Liveness check for the frontend container itself (used by Docker health checks).
// It does not call the backend: the backend has its own check at /api/health.
export function GET() {
  return Response.json({ status: "ok" });
}
