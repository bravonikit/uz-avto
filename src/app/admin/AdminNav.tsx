"use client";
// Вкладки админки. Цифра рядом с названием: сколько всего ждёт решения.

import Link from "next/link";
import { usePathname } from "next/navigation";

type Props = { waiting: number; review: number; showLogout: boolean; logout: () => Promise<void> };

export function AdminNav({ waiting, review, showLogout, logout }: Props) {
  const pathname = usePathname();
  const tabs = [
    { href: "/admin", label: "Заявки", count: waiting },
    { href: "/admin/review", label: "Ручной разбор", count: review },
    { href: "/admin/channel", label: "Канал", count: 0 },
  ];
  return (
    <nav className="mb-6 flex flex-wrap items-center gap-2">
      {tabs.map((tab) => {
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`rounded-full px-4 py-2 text-sm font-medium ${
              active ? "bg-slate-900 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
            }`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className={`ml-2 rounded-full px-1.5 text-xs ${active ? "bg-white/20" : "bg-brand-600 text-white"}`}>
                {tab.count}
              </span>
            )}
          </Link>
        );
      })}
      {showLogout && (
        <form action={logout} className="ml-auto">
          <button type="submit" className="text-sm text-slate-500 hover:text-slate-900">
            Выйти
          </button>
        </form>
      )}
    </nav>
  );
}
