// Каркас админки: проверка входа и вкладки. Адрес: /admin
// Кто может войти, описано в src/lib/admin.ts.

import type { Metadata } from "next";
import { Suspense } from "react";
import { adminMode, isAdmin } from "@/lib/admin";
import { getModelQueue } from "@/lib/model-review";
import { getPairQueue, getPriceQueue } from "@/lib/review";
import { getAllSellerListings } from "@/lib/seller-listings";
import { logout } from "./actions";
import { AdminNav } from "./AdminNav";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = {
  title: "Админка",
  robots: { index: false, follow: false }, // поисковикам сюда не надо
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Suspense fallback={<p className="text-slate-400">Загружаем…</p>}>
        <Gate>{children}</Gate>
      </Suspense>
    </div>
  );
}

async function Gate({ children }: { children: React.ReactNode }) {
  const mode = adminMode();
  if (mode === "closed") {
    return (
      <p className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">
        Админка закрыта: на сервере не задан пароль. Добавьте строку ADMIN_PASSWORD=... в файл .env.local и
        перезапустите сайт.
      </p>
    );
  }
  if (!(await isAdmin())) return <LoginForm />;

  const [listings, pairs, prices, models] = await Promise.all([
    getAllSellerListings(),
    getPairQueue(),
    getPriceQueue(),
    getModelQueue(),
  ]);
  return (
    <>
      <AdminNav
        waiting={listings.filter((listing) => listing.status === "moderation").length}
        review={pairs.pairs.length + prices.suspects.length}
        models={models.items.length}
        showLogout={mode === "password"}
        logout={logout}
      />
      {mode === "open" && (
        <p className="mb-6 rounded-xl bg-amber-50 px-4 py-2 text-xs text-amber-800">
          Пароль не задан: админка открыта, потому что сайт запущен локально (npm run dev). Перед выкладкой на
          сервер добавьте ADMIN_PASSWORD в .env.local.
        </p>
      )}
      {children}
    </>
  );
}
