"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ApiRequestError } from "@/lib/api";
import {
  Row,
  archiveResource,
  createResource,
  listResource,
} from "@/lib/networkApi";

export interface FieldDef {
  name: string;
  label: string;
  type?: "text" | "number" | "select";
  required?: boolean;
  options?: { value: string; label: string }[]; // static (enum)
  optionsFrom?: string; // resource path to load options (FK)
  optionLabel?: string; // field to show as label (default "code" or "name")
}

export interface ColumnDef {
  key: string;
  label: string;
}

interface Props {
  title: string;
  path: string;
  columns: ColumnDef[];
  fields: FieldDef[];
}

export function ResourceManager({ title, path, columns, fields }: Props) {
  const [rows, setRows] = useState<Row[]>([]);
  const [fkOptions, setFkOptions] = useState<Record<string, Row[]>>({});
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    listResource(path).then(setRows).catch(() => setError("Failed to load"));
  }, [path]);

  useEffect(() => {
    refresh();
    // Load FK option lists.
    fields
      .filter((f) => f.optionsFrom)
      .forEach((f) =>
        listResource(f.optionsFrom!)
          .then((opts) => setFkOptions((p) => ({ ...p, [f.name]: opts })))
          .catch(() => undefined),
      );
  }, [refresh, fields]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const body: Record<string, unknown> = {};
    for (const f of fields) {
      const v = form[f.name];
      if (v === undefined || v === "") continue;
      body[f.name] = f.type === "number" ? Number(v) : v;
    }
    try {
      await createResource(path, body);
      setForm({});
      refresh();
    } catch (err) {
      setError(
        err instanceof ApiRequestError
          ? `${err.error.message}${err.error.details ? ` — ${JSON.stringify(err.error.details)}` : ""}`
          : "Create failed",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onArchive(id: string) {
    await archiveResource(path, id).catch(() => setError("Archive failed"));
    refresh();
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">{title}</h1>
      {error && <p className="mb-3 rounded bg-red-950 px-3 py-2 text-sm text-red-300">{error}</p>}

      <form onSubmit={onSubmit} className="mb-6 flex flex-wrap items-end gap-3 rounded-lg bg-panel p-4">
        {fields.map((f) => (
          <label key={f.name} className="text-sm">
            <span className="mb-1 block text-slate-400">{f.label}{f.required && " *"}</span>
            {f.type === "select" || f.optionsFrom ? (
              <select
                required={f.required}
                value={form[f.name] ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, [f.name]: e.target.value }))}
                className="w-44 rounded border border-slate-700 bg-surface px-2 py-1.5"
              >
                <option value="">—</option>
                {(f.options ?? []).map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
                {(fkOptions[f.name] ?? []).map((o) => (
                  <option key={o.id} value={o.id}>
                    {String(o[f.optionLabel ?? "code"] ?? o["name"] ?? o.id)}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={f.type ?? "text"}
                required={f.required}
                value={form[f.name] ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, [f.name]: e.target.value }))}
                className="w-44 rounded border border-slate-700 bg-surface px-2 py-1.5"
              />
            )}
          </label>
        ))}
        <button type="submit" disabled={busy} className="rounded bg-sky-600 px-4 py-2 text-sm hover:bg-sky-500 disabled:opacity-50">
          {busy ? "Saving…" : "Add"}
        </button>
      </form>

      <div className="overflow-x-auto rounded-lg bg-panel">
        <table className="w-full text-left text-sm">
          <thead className="text-slate-400">
            <tr>
              {columns.map((c) => <th key={c.key} className="p-3">{c.label}</th>)}
              <th className="p-3">Active</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-800">
                {columns.map((c) => <td key={c.key} className="p-3">{String(r[c.key] ?? "—")}</td>)}
                <td className="p-3">{r.is_active ? "yes" : "no"}</td>
                <td className="p-3">
                  {r.is_active !== false && (
                    <button onClick={() => onArchive(r.id)} className="text-xs text-slate-400 hover:text-red-400">
                      Archive
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
