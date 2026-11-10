import Link from "next/link";

export function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        <Link href="/" className="text-xl font-extrabold tracking-tight text-slate-900">
          Mashina<span className="text-emerald-600">.</span>
        </Link>
        <nav className="flex flex-1 items-center gap-4 text-sm text-slate-600">
          <Link href="/cars" className="hover:text-slate-900">
            Все объявления
          </Link>
        </nav>
        <Link
          href="/sell"
          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
        >
          <span className="sm:hidden">+ Подать</span>
          <span className="hidden sm:inline">+ Подать объявление</span>
        </Link>
      </div>
    </header>
  );
}
