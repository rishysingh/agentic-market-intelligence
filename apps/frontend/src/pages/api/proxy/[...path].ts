import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const pathSegments = req.query.path;
  const subPath = Array.isArray(pathSegments) ? pathSegments.join("/") : pathSegments || "";
  const backendBase =
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://127.0.0.1:8080";

  const queryParams = new URLSearchParams();
  Object.entries(req.query).forEach(([k, v]) => {
    if (k !== "path" && v !== undefined) {
      queryParams.set(k, Array.isArray(v) ? v[0] : v);
    }
  });
  const qs = queryParams.toString();
  const targetUrl = `${backendBase.replace(/\/$/, "")}/api/v1/${subPath}${qs ? `?${qs}` : ""}`;

  try {
    const fetchOpts: RequestInit = {
      method: req.method || "GET",
      headers: {
        "Content-Type": "application/json",
      },
    };
    if (req.method === "POST" && req.body) {
      fetchOpts.body = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
    }
    const upstream = await fetch(targetUrl, fetchOpts);
    const data = await upstream.json();
    res.status(upstream.status).json(data);
  } catch (err: any) {
    res.status(502).json({
      error: "Failed to reach Tier-2 Backend API",
      detail: err?.message || String(err),
      targetUrl,
    });
  }
}
