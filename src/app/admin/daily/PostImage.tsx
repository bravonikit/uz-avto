"use client";
// Картинка поста для Telegram, 1080 на 1350, рисуется прямо в браузере на canvas.
// Две раскладки: list (список из 5 машин с ценой рынка, пост «Ниже рынка») и tiles (одна большая плитка
// и четыре поменьше, посты «Самые красивые» и «Подборка дня»).
// Оформление повторяет макеты от 16.11.2026 (parser/data/_scratch/tg_post_2026-11-16).

import { useEffect, useRef, useState } from "react";
import { publishPostAction } from "../actions";

export type PostImageItem = {
  title: string;
  sub: string; // "2025 · 8 700 км"
  price: string; // "66 900$"
  market?: string; // "82 450$"
  cheaper?: string; // "15 550$"
  image?: string; // "/tg/tg-aslauto-3923.jpg"
  cutTop?: boolean; // у канала цена или баннер в верхней части фото: рамку прижимаем к низу кадра
};

type Props = {
  layout: "list" | "tiles";
  kicker: string; // мелкая строка над заголовком: "ТОП 5 ЗА СУТКИ"
  title: string; // "Ниже рынка 💸"
  footer: string;
  date: string;
  items: PostImageItem[];
  fileName: string;
  caption?: string; // подпись к посту в канале
  channel?: string; // "@uzavto_daily"; нет: бот не настроен, кнопки публикации нет
  published?: { url?: string; at: string }; // этот пост уже уходил в канал
};

const WIDTH = 1080;
const HEIGHT = 1350;
const SIDE = 56; // поля слева и справа
const GREY = "#8a8f98";
const INK = "#111111";

function loadImage(src?: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    if (!src) return resolve(null);
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null);
    image.src = src;
  });
}

function roundedPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// Фото заполняет рамку целиком, лишнее обрезается по краям. Нет фото: серая плашка.
function drawPhoto(
  ctx: CanvasRenderingContext2D,
  image: HTMLImageElement | null,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
  cutTop = false,
) {
  ctx.save();
  roundedPath(ctx, x, y, w, h, r);
  ctx.clip();
  ctx.fillStyle = "#e5e7eb";
  ctx.fillRect(x, y, w, h);
  if (image) {
    const scale = Math.max(w / image.naturalWidth, h / image.naturalHeight);
    const sw = w / scale;
    const sh = h / scale;
    const sy = cutTop ? image.naturalHeight - sh : (image.naturalHeight - sh) / 2;
    ctx.drawImage(image, (image.naturalWidth - sw) / 2, sy, sw, sh, x, y, w, h);
  }
  ctx.restore();
}

// Обрезает строку с многоточием, чтобы она влезла в ширину
function fit(ctx: CanvasRenderingContext2D, text: string, maxWidth: number) {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let cut = text;
  while (cut.length > 1 && ctx.measureText(`${cut}…`).width > maxWidth) cut = cut.slice(0, -1);
  return `${cut.trimEnd()}…`;
}

function badge(ctx: CanvasRenderingContext2D, font: (size: number, weight: number) => string, n: number, x: number, y: number, dark: boolean) {
  roundedPath(ctx, x, y, 40, 40, 10);
  ctx.fillStyle = dark ? INK : "#ffffff";
  ctx.fill();
  ctx.fillStyle = dark ? "#ffffff" : INK;
  ctx.font = font(22, 800);
  ctx.textAlign = "center";
  ctx.fillText(String(n), x + 20, y + 28);
  ctx.textAlign = "left";
}

async function draw(canvas: HTMLCanvasElement, { layout, kicker, title, footer, date, items }: Props) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  await document.fonts.ready;
  const family = getComputedStyle(document.body).fontFamily || "sans-serif";
  const font = (size: number, weight: number) => `${weight} ${size}px ${family}`;
  const images = await Promise.all(items.map((item) => loadImage(item.image)));

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  ctx.textBaseline = "alphabetic";

  // Шапка
  ctx.fillStyle = GREY;
  ctx.font = font(22, 700);
  (ctx as CanvasRenderingContext2D & { letterSpacing?: string }).letterSpacing = "3px";
  ctx.fillText(kicker, SIDE, 78);
  (ctx as CanvasRenderingContext2D & { letterSpacing?: string }).letterSpacing = "0px";
  ctx.fillStyle = GREY;
  ctx.font = font(24, 500);
  ctx.textAlign = "right";
  ctx.fillText(date, WIDTH - SIDE, 145);
  const titleWidth = WIDTH - SIDE * 2 - ctx.measureText(date).width - 28;
  ctx.textAlign = "left";
  // Длинный заголовок уменьшаем, пока не поместится слева от даты
  ctx.fillStyle = INK;
  let titleSize = 60;
  ctx.font = font(titleSize, 800);
  while (titleSize > 34 && ctx.measureText(title).width > titleWidth) {
    titleSize -= 2;
    ctx.font = font(titleSize, 800);
  }
  ctx.fillText(fit(ctx, title, titleWidth), SIDE, 142);

  if (layout === "list") {
    const rowHeight = 213;
    items.slice(0, 5).forEach((item, index) => {
      const top = 180 + index * rowHeight;
      ctx.fillStyle = "#ececee";
      ctx.fillRect(SIDE, top, WIDTH - SIDE * 2, 1);
      drawPhoto(ctx, images[index], SIDE, top + 18, 250, 176, 18, item.cutTop);
      badge(ctx, font, index + 1, SIDE + 10, top + 28, true);

      // Справа: цена, цена рынка зачёркнута, зелёная плашка с выгодой
      ctx.textAlign = "right";
      ctx.fillStyle = INK;
      ctx.font = font(42, 800);
      ctx.fillText(item.price, WIDTH - SIDE, top + 84);
      const priceWidth = ctx.measureText(item.price).width;
      if (item.market) {
        ctx.fillStyle = GREY;
        ctx.font = font(20, 500);
        const text = `рынок ${item.market}`;
        ctx.fillText(text, WIDTH - SIDE, top + 118);
        const width = ctx.measureText(text).width;
        ctx.fillRect(WIDTH - SIDE - width, top + 111, width, 1.5);
      }
      let pillWidth = 0;
      if (item.cheaper) {
        ctx.font = font(22, 700);
        const text = `дешевле на ${item.cheaper}`;
        pillWidth = ctx.measureText(text).width + 26;
        roundedPath(ctx, WIDTH - SIDE - pillWidth, top + 131, pillWidth, 38, 12);
        ctx.fillStyle = "#e8f8ee";
        ctx.fill();
        ctx.fillStyle = "#15803d";
        ctx.fillText(text, WIDTH - SIDE - 13, top + 158);
      }
      ctx.textAlign = "left";

      // Посередине: название и год с пробегом, место ограничено блоком цены
      const textLeft = SIDE + 278;
      const textWidth = WIDTH - SIDE - Math.max(priceWidth, pillWidth) - 24 - textLeft;
      ctx.fillStyle = INK;
      ctx.font = font(34, 700);
      ctx.fillText(fit(ctx, item.title, textWidth), textLeft, top + 102);
      ctx.fillStyle = GREY;
      ctx.font = font(24, 500);
      ctx.fillText(fit(ctx, item.sub, textWidth), textLeft, top + 138);
    });
    ctx.fillStyle = "#a3a7ae";
    ctx.font = font(19, 500);
    ctx.fillText(footer, SIDE, 1305);
  } else {
    // Одна большая плитка и четыре поменьше
    const tiles = [
      { x: SIDE, y: 180, w: 968, h: 514, big: true },
      { x: SIDE, y: 712, w: 476, h: 280, big: false },
      { x: SIDE + 492, y: 712, w: 476, h: 280, big: false },
      { x: SIDE, y: 1008, w: 476, h: 280, big: false },
      { x: SIDE + 492, y: 1008, w: 476, h: 280, big: false },
    ];
    items.slice(0, 5).forEach((item, index) => {
      const { x, y, w, h, big } = tiles[index];
      drawPhoto(ctx, images[index], x, y, w, h, 24, item.cutTop);
      // Затемнение снизу, чтобы белый текст читался на любом фото
      ctx.save();
      roundedPath(ctx, x, y, w, h, 24);
      ctx.clip();
      const shade = ctx.createLinearGradient(0, y + h * 0.35, 0, y + h);
      shade.addColorStop(0, "rgba(0,0,0,0)");
      shade.addColorStop(1, "rgba(0,0,0,0.78)");
      ctx.fillStyle = shade;
      ctx.fillRect(x, y, w, h);
      ctx.restore();
      badge(ctx, font, index + 1, x + 16, y + 16, false);

      const left = x + 22;
      const width = w - 44;
      ctx.fillStyle = "#ffffff";
      ctx.font = font(big ? 52 : 34, 800);
      ctx.fillText(item.price, left, y + h - (big ? 34 : 26));
      ctx.fillStyle = "rgba(255,255,255,0.82)";
      ctx.font = font(big ? 24 : 19, 500);
      ctx.fillText(fit(ctx, item.sub, width), left, y + h - (big ? 96 : 70));
      ctx.fillStyle = "#ffffff";
      ctx.font = font(big ? 40 : 28, 700);
      ctx.fillText(fit(ctx, item.title, width), left, y + h - (big ? 130 : 96));
    });
    ctx.fillStyle = "#a3a7ae";
    ctx.font = font(19, 500);
    ctx.fillText(footer, SIDE, 1320);
  }
}

type PublishState = "idle" | "confirm" | "sending" | "sent" | "error";

export function PostImage(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { layout, kicker, title, footer, date, items, fileName, caption, channel, published } = props;
  const [copyLabel, setCopyLabel] = useState("Скопировать");
  const [state, setState] = useState<PublishState>("idle");
  const [error, setError] = useState("");
  const [sentUrl, setSentUrl] = useState<string | undefined>(published?.url);
  const wasSent = Boolean(published) || state === "sent";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    // data-ready: картинка дорисована (фото загружены). По нему автопостинг parser/post_daily.py ждёт холст
    delete canvas.dataset.ready;
    void draw(canvas, { layout, kicker, title, footer, date, items, fileName }).then(() => {
      canvas.dataset.ready = "1";
    });
  }, [layout, kicker, title, footer, date, items, fileName]);

  const toBlob = (type = "image/png", quality?: number) =>
    new Promise<Blob | null>((resolve) =>
      canvasRef.current ? canvasRef.current.toBlob(resolve, type, quality) : resolve(null),
    );

  const download = async () => {
    const blob = await toBlob();
    if (!blob) return;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  // Копирование картинки работает только на localhost или https: по адресу 10.x.x.x браузер не даёт буфер
  const copy = async () => {
    try {
      const blob = await toBlob();
      if (!blob || !navigator.clipboard) throw new Error("нет буфера");
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      setCopyLabel("Скопировано ✓");
    } catch {
      setCopyLabel("Не дал браузер, скачайте");
    }
    setTimeout(() => setCopyLabel("Скопировать"), 2500);
  };

  // В канал уходит JPEG: в несколько раз легче PNG, Telegram всё равно пережимает картинку
  const publish = async () => {
    setState("sending");
    setError("");
    const blob = await toBlob("image/jpeg", 0.92);
    if (!blob || caption === undefined) {
      setState("error");
      setError("картинка не готова");
      return;
    }
    const form = new FormData();
    form.append("key", fileName.replace(/\.png$/, ""));
    form.append("photo", blob, fileName.replace(/\.png$/, ".jpg"));
    form.append("caption", caption);
    try {
      const result = await publishPostAction(form);
      if (result.error) throw new Error(result.error);
      setSentUrl(result.url);
      setState("sent");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
      setState("error");
    }
  };

  // Первый раз публикуем сразу; повторно (пост уже в канале) только после «Да»
  const onPublish = () => (wasSent && state !== "confirm" ? setState("confirm") : void publish());

  const publishLabel = {
    idle: wasSent ? "Опубликовать ещё раз" : "Опубликовать в канал",
    confirm: "Да, выложить повторно",
    sending: "Публикую…",
    sent: "Опубликовано ✓",
    error: "Повторить публикацию",
  }[state];

  const link = sentUrl ?? published?.url;

  return (
    <div>
      <canvas ref={canvasRef} width={WIDTH} height={HEIGHT} className="w-full max-w-md rounded-2xl ring-1 ring-slate-200" />
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <button type="button" onClick={download} className="rounded-xl bg-slate-900 px-4 py-2 font-semibold text-white transition hover:bg-slate-700 active:scale-95">
          Скачать картинку
        </button>
        <button type="button" onClick={copy} className="rounded-xl px-4 py-2 font-medium text-slate-700 ring-1 ring-slate-300 transition hover:bg-slate-50 active:scale-95">
          {copyLabel}
        </button>
        {channel && caption !== undefined && (
          <button
            type="button"
            onClick={onPublish}
            disabled={state === "sending" || state === "sent"}
            data-state={state}
            className={`rounded-xl px-4 py-2 font-semibold text-white transition active:scale-95 disabled:cursor-default ${
              state === "sent" ? "bg-emerald-600" : state === "sending" ? "animate-pulse bg-brand-600" : "bg-brand-600 hover:bg-brand-700"
            }`}
          >
            {publishLabel}
          </button>
        )}
        {state === "confirm" && (
          <button type="button" onClick={() => setState("idle")} className="rounded-xl px-3 py-2 text-slate-600 ring-1 ring-slate-300">
            Отмена
          </button>
        )}
      </div>
      {state === "error" && <p className="mt-2 text-xs text-red-700">Не опубликовано: {error}</p>}
      {wasSent && (
        <p className="mt-2 text-xs text-emerald-700">
          {state === "sent" ? "Пост в канале" : `Уже в канале с ${new Date(published!.at).toLocaleString("ru-RU")}`}
          {link?.startsWith("http") && (
            <>
              :{" "}
              <a href={link} target="_blank" rel="noreferrer" className="underline">
                открыть пост
              </a>
            </>
          )}
        </p>
      )}
      {!channel && (
        <p className="mt-2 text-xs text-slate-400">Кнопки «в канал» нет: бот не настроен (TG_BOT_TOKEN и TG_CHANNEL, python parser/tg_bot.py setup)</p>
      )}
    </div>
  );
}
