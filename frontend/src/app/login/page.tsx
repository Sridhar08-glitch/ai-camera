"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiRequestError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiRequestError
          ? err.error.message
          : "Login failed. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-xl bg-panel p-8 shadow-lg"
      >
        <h1 className="mb-6 text-xl font-semibold">Traffic Operations Center</h1>
        {error && (
          <p className="mb-4 rounded bg-red-950 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}
        <label className="mb-4 block text-sm">
          <span className="mb-1 block text-slate-400">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded border border-slate-700 bg-surface px-3 py-2"
          />
        </label>
        <label className="mb-6 block text-sm">
          <span className="mb-1 block text-slate-400">Password</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded border border-slate-700 bg-surface px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-sky-600 py-2 font-medium hover:bg-sky-500 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
