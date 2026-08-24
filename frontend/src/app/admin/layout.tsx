"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

const ADMIN_NAV = [
  { href: "/admin/observability", label: "Observability" },
  { href: "/admin/audit", label: "Audit Log" },
  { href: "/admin/retention", label: "Retention" },
  { href: "/admin/registry", label: "Model Registry" },
];

const NETWORK_NAV = [
  { href: "/admin/network/cities", label: "Cities" },
  { href: "/admin/network/zones", label: "Zones" },
  { href: "/admin/network/roads", label: "Roads" },
  { href: "/admin/network/road-segments", label: "Road Segments" },
  { href: "/admin/network/intersections", label: "Intersections" },
  { href: "/admin/network/lanes", label: "Lanes" },
  { href: "/admin/network/cameras", label: "Cameras" },
];

const ADMIN_ROLES = ["system_admin", "traffic_admin"];
// Roles allowed into the admin shell at all (viewer excluded).
const SECTION_ROLES = ["system_admin", "traffic_admin", "traffic_operator"];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  const role = user?.role ?? "";
  const allowed = SECTION_ROLES.includes(role);
  const isAdmin = ADMIN_ROLES.includes(role);

  useEffect(() => {
    if (loading) return;
    // Server enforces authorization; this is cosmetic redirect only.
    if (!user) router.replace("/login");
    else if (!allowed) router.replace("/dashboard");
  }, [user, loading, allowed, router]);

  if (loading || !user || !allowed) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-slate-400">Loading…</p>
      </main>
    );
  }

  // system_admin sees all platform tools; traffic_admin sees observability only.
  const platformNav =
    role === "system_admin"
      ? ADMIN_NAV
      : role === "traffic_admin"
        ? ADMIN_NAV.filter((n) => n.href === "/admin/observability")
        : [];

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 bg-panel p-4">
        <Link href="/dashboard" className="mb-6 block text-lg font-semibold">
          ← Platform Admin
        </Link>
        <nav className="space-y-1">
          {platformNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              {item.label}
            </Link>
          ))}
          {isAdmin && (
            <>
              <p className="mt-4 mb-1 px-3 text-xs uppercase tracking-wide text-slate-500">Network</p>
              {NETWORK_NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="block rounded px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
                >
                  {item.label}
                </Link>
              ))}
            </>
          )}
          <p className="mt-4 mb-1 px-3 text-xs uppercase tracking-wide text-slate-500">Media</p>
          <Link href="/admin/videos" className="block rounded px-3 py-2 text-sm text-slate-300 hover:bg-slate-800">
            Videos
          </Link>
          <Link href="/admin/processing" className="block rounded px-3 py-2 text-sm text-slate-300 hover:bg-slate-800">
            Processing
          </Link>
        </nav>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
