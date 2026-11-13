// Счётчик просмотров страниц. Пока базы данных нет, числа лежат в файле
// .data/views.json на компьютере, где запущен сайт (в git он не попадает).
// Когда появится база, поменяется только этот файл.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const FILE = path.join(process.cwd(), ".data", "views.json");

type Views = { total: number; pages: Record<string, number> };

async function load(): Promise<Views> {
  try {
    const saved = JSON.parse(await readFile(FILE, "utf8")) as Partial<Views>;
    return { total: saved.total ?? 0, pages: saved.pages ?? {} };
  } catch {
    return { total: 0, pages: {} }; // файла ещё нет: считаем с нуля
  }
}

// Запросы обрабатываем по очереди, чтобы два просмотра сразу не затёрли друг друга
let queue: Promise<unknown> = Promise.resolve();

// Засчитывает один просмотр страницы и возвращает общее число просмотров сайта
export function addView(page: string): Promise<number> {
  const result = queue.then(async () => {
    const views = await load();
    views.total += 1;
    views.pages[page] = (views.pages[page] ?? 0) + 1;
    await mkdir(path.dirname(FILE), { recursive: true });
    await writeFile(FILE, JSON.stringify(views, null, 2));
    return views.total;
  });
  queue = result.catch(() => undefined);
  return result;
}
