"use server";
// Действия в админке. Выполняются только на сервере, каждое сначала проверяет, что это админ.

import { refresh } from "next/cache";
import { isAdmin, signInAdmin, signOutAdmin } from "@/lib/admin";
import { parseNumber } from "@/lib/format";
import { decidePair, decidePrice, getPriceQueue } from "@/lib/review";
import { setSellerListingStatus } from "@/lib/seller-listings";

export type LoginState = { error?: string };

export async function login(_prevState: LoginState, formData: FormData): Promise<LoginState> {
  const entered = formData.get("password");
  if (typeof entered !== "string" || !(await signInAdmin(entered))) return { error: "Неверный пароль" };
  refresh();
  return {};
}

export async function logout() {
  await signOutAdmin();
  refresh();
}

// Заявка продавца: опубликовать, отклонить с причиной, снять с публикации или вернуть на проверку
export async function moderateListing(formData: FormData) {
  if (!(await isAdmin())) return;
  const id = formData.get("id");
  const decision = formData.get("decision");
  const reason = formData.get("reason");
  if (typeof id !== "string") return;
  if (decision === "publish") await setSellerListingStatus(id, "active");
  else if (decision === "reject") {
    await setSellerListingStatus(id, "rejected", typeof reason === "string" ? reason.trim().slice(0, 300) : undefined);
  } else if (decision === "review") await setSellerListingStatus(id, "moderation");
  refresh();
}

// Пара «похоже на одну машину»: одна это машина или разные
export async function decidePairAction(formData: FormData) {
  if (!(await isAdmin())) return;
  const first = formData.get("first");
  const second = formData.get("second");
  const decision = formData.get("decision");
  if (typeof first !== "string" || typeof second !== "string") return;
  if (decision !== "same" && decision !== "different") return;
  await decidePair(first, second, decision);
  refresh();
}

// Странная цена: оставить как есть, исправить или отметить, что цены в посте нет
export async function decidePriceAction(formData: FormData) {
  if (!(await isAdmin())) return;
  const id = formData.get("id");
  const decision = formData.get("decision");
  if (typeof id !== "string") return;
  if (decision === "none") await decidePrice(id, null);
  else if (decision === "keep") {
    const suspect = (await getPriceQueue()).suspects.find((item) => item.id === id);
    if (suspect?.price) await decidePrice(id, suspect.price);
  } else if (decision === "fix") {
    const price = parseNumber(formData.get("price"));
    if (price && price >= 500 && price <= 5_000_000) await decidePrice(id, price);
  }
  refresh();
}
