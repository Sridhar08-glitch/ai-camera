"use client";

import { useEffect, useState } from "react";
import { config } from "@/lib/config";

type Check = { ok: boolean; error?: string };
type Readyz = {
  status: string;
  checks: Record<string, Check>;
};

export function HealthWidget() {
  const [data, setData] = useState<Readyz | null>(null);
  const [reachable, setReachable] = useState(true);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const res = await fetch(`${config.apiRoot}/readyz`);
        const body = await res.json();
        if (active) {
          setData(body.data ?? body);
          setReachable(true);
        }
      } catch {
        if (active) setReachable(false);
      }
    }
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="rounded-lg bg-panel p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-300">
        Infrastructure
      </h2>
      {!reachable && <p className="text-sm text-red-400">Backend unreachable</p>}
      {reachable && data && (
        <ul className="space-y-1 text-sm">
          {Object.entries(data.checks).map(([name, c]) => (
            <li key={name} className="flex items-center justify-between">
              <span className="text-slate-400">{name}</span>
              <span className={c.ok ? "text-emerald-400" : "text-red-400"}>
                {c.ok ? "healthy" : "down"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
