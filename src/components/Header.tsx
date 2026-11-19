import Link from "next/link";
import { IS_PREVIEW, PREVIEW_DAY } from "@/lib/listings";

export function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:gap-6">
        <Link href="/" className="text-xl font-extrabold tracking-tight text-slate-900">
          Mashina Bashina<span className="text-brand-600">.</span>
        </Link>
        {IS_PREVIEW && (
          <Link
            href={PREVIEW_DAY ? `/cars?day=${PREVIEW_DAY}&hideSold=1` : "/cars"}
            className="rounded-full bg-brand-600 px-3 py-1 text-xs font-bold text-white"
          >
            СТАЛО{PREVIEW_DAY ? ` · ${PREVIEW_DAY}` : ""}
          </Link>
        )}
        <nav className="flex flex-1 items-center gap-4 text-sm text-slate-600">
          <Link href="/cars" className="hover:text-slate-900">
            Все объявления
          </Link>
        </nav>
        {/* Кабинет продавца: на телефоне значок, на широком экране ещё и подпись */}
        <Link
          href="/cabinet"
          aria-label="Кабинет продавца"
          className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6" aria-hidden="true">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6" strokeLinecap="round" />
          </svg>
          <span className="hidden sm:inline">Кабинет</span>
        </Link>
        <Link
          href="/sell"
          className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold whitespace-nowrap text-white hover:bg-brand-700"
        >
          <span className="sm:hidden">+ Подать</span>
          <span className="hidden sm:inline">+ Подать объявление</span>
        </Link>
      </div>
    </header>
  );
}
