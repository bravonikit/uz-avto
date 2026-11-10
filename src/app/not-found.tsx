import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-20 text-center">
      <p className="text-6xl font-extrabold text-slate-300">404</p>
      <h1 className="mt-4 text-2xl font-bold">Такой страницы нет</h1>
      <p className="mt-2 text-slate-500">Возможно, объявление уже снято с продажи.</p>
      <Link
        href="/cars"
        className="mt-6 inline-block rounded-xl bg-emerald-600 px-5 py-2.5 font-semibold text-white hover:bg-emerald-700"
      >
        К объявлениям
      </Link>
    </div>
  );
}
