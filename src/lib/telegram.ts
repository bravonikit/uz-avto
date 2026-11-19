// Публикация постов «Аналитики дня» в открытый Telegram канал через бота проекта.
// Токен и канал: TG_BOT_TOKEN и TG_CHANNEL в .env.local, а если там нет, то из parser/.env
// (одна запись на весь проект, её заполняет python parser/tg_bot.py setup).
// Что уже опубликовано, лежит в .data/tg-posts.json (в git не попадает): так админка видит,
// что пост дня уже ушёл, и не даёт случайно выложить его второй раз.

import { readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const LOG_FILE = path.join(process.cwd(), ".data", "tg-posts.json");
const CAPTION_LIMIT = 1024; // столько Telegram разрешает в подписи к фото
const TEXT_LIMIT = 4096;

export type PublishedPost = { key: string; channel: string; messageIds: number[]; url?: string; at: string };

function parserEnv(): Record<string, string> {
  try {
    const text = readFileSync(path.join(process.cwd(), "parser", ".env"), "utf-8");
    const values: Record<string, string> = {};
    for (const line of text.split("\n")) {
      const match = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
      if (match) values[match[1]] = match[2].replace(/^["']|["']$/g, "");
    }
    return values;
  } catch {
    return {};
  }
}

export function telegramConfig(): { token?: string; channel?: string } {
  const env = parserEnv();
  return {
    token: process.env.TG_BOT_TOKEN || env.TG_BOT_TOKEN || undefined,
    channel: process.env.TG_CHANNEL || env.TG_CHANNEL || undefined,
  };
}

// Канал для показа в админке: "@uzavto_daily" или undefined, если бот не настроен
export function telegramChannel(): string | undefined {
  const { token, channel } = telegramConfig();
  return token && channel ? channel : undefined;
}

export async function publishedPosts(): Promise<Record<string, PublishedPost>> {
  try {
    return JSON.parse(await readFile(LOG_FILE, "utf-8"));
  } catch {
    return {};
  }
}

async function call<T>(token: string, method: string, body: FormData | object): Promise<T> {
  const isForm = body instanceof FormData;
  const response = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    body: isForm ? body : JSON.stringify(body),
    headers: isForm ? undefined : { "Content-Type": "application/json" },
  });
  const data = await response.json().catch(() => ({}));
  if (!data.ok) throw new Error(data.description || `Telegram ответил ${response.status}`);
  return data.result as T;
}

// Ссылка на пост: у открытого канала t.me/<имя>/<номер>
function postUrl(channel: string, messageId: number) {
  return channel.startsWith("@") ? `https://t.me/${channel.slice(1)}/${messageId}` : undefined;
}

// Картинка с подписью. Подпись длиннее 1024 знаков: у картинки только первая строка,
// весь текст ответом на неё вторым сообщением (ссылки на машины не теряются).
export async function publishToChannel(key: string, photo: Blob, caption: string): Promise<PublishedPost> {
  const { token, channel } = telegramConfig();
  if (!token || !channel) throw new Error("Бот не настроен: нет TG_BOT_TOKEN или TG_CHANNEL (python parser/tg_bot.py setup)");

  const short = caption.length <= CAPTION_LIMIT;
  const form = new FormData();
  form.append("chat_id", channel);
  form.append("photo", photo, `${key}.jpg`);
  form.append("caption", short ? caption : caption.split("\n")[0]);
  const sent = await call<{ message_id: number }>(token, "sendPhoto", form);
  const messageIds = [sent.message_id];
  if (!short) {
    const rest = await call<{ message_id: number }>(token, "sendMessage", {
      chat_id: channel,
      text: caption.split("\n").slice(1).join("\n").trim().slice(0, TEXT_LIMIT),
      reply_parameters: { message_id: sent.message_id },
      link_preview_options: { is_disabled: true },
    });
    messageIds.push(rest.message_id);
  }

  const post: PublishedPost = { key, channel, messageIds, url: postUrl(channel, sent.message_id), at: new Date().toISOString() };
  const log = await publishedPosts();
  log[key] = post;
  await mkdir(path.dirname(LOG_FILE), { recursive: true });
  await writeFile(LOG_FILE, JSON.stringify(log, null, 2));
  return post;
}
