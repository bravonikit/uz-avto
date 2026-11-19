"use server";
// Действия в админке. Выполняются только на сервере, каждое сначала проверяет, что это админ.

import { refresh } from "next/cache";
import { isAdmin, signInAdmin, signOutAdmin } from "@/lib/admin";
import { parseNumber } from "@/lib/format";
import { decidePair, decidePrice, getPriceQueue } from "@/lib/review";
import { setSellerListingStatus } from "@/lib/seller-listings";
import { publishToChannel } from "@/lib/telegram";

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

export type PublishState = { error?: string; url?: string };

// Пост «Аналитики дня» в открытый Telegram канал: картинка с холста в админке и подпись к ней
export async function publishPostAction(formData: FormData): Promise<PublishState> {
  if (!(await isAdmin())) return { error: "Нужен вход в админку" };
  const key = formData.get("key");
  const photo = formData.get("photo");
  const caption = formData.get("caption");
  if (typeof key !== "string" || !(photo instanceof Blob) || typeof caption !== "string") return { error: "Пустой пост" };
  // Пока у сайта нет домена, ссылки в подписи ведут на заглушку: такие строки в канал не отправляем
  const clean = caption
    .split("\n")
    .filter((line) => !line.includes("АДРЕС-САЙТА"))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  try {
    const post = await publishToChannel(key, photo, clean);
    refresh();
    return { url: post.url ?? post.channel };
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
}
