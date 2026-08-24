"use client";

import { useEffect, useState } from "react";
import { AuditEvent, listAuditEvents } from "@/lib/adminApi";

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAuditEvents()
      .then(setEvents)
      .catch(() => setError("Failed to load audit events"));
  }, []);

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Audit Log</h1>
      {error && <p className="text-red-400">{error}</p>}
      <div className="overflow-x-auto rounded-lg bg-panel">
        <table className="w-full text-left text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="p-3">Time</th>
              <th className="p-3">Event</th>
              <th className="p-3">Outcome</th>
              <th className="p-3">Actor</th>
              <th className="p-3">Target</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-t border-slate-800">
                <td className="p-3 text-slate-400">{e.created_at}</td>
                <td className="p-3">{e.event_type}</td>
                <td className="p-3">{e.outcome}</td>
                <td className="p-3">{e.actor_email || "—"}</td>
                <td className="p-3">{e.target_type || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
