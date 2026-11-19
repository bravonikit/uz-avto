import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Второй сайт «стало» (npm run dev:new) собирается в свою папку, чтобы два сайта работали одновременно
  distDir: process.env.NEXT_DIST_DIR || ".next",
  cacheComponents: true,
  // Сайт в режиме разработки открывают и по адресу Мака в сети (http://10.20.52.247:3000, с телефона).
  // Без этого Next блокирует скрипты страницы для чужого адреса: кнопки не работают, картинки дня пустые
  allowedDevOrigins: ["10.*.*.*", "192.168.*.*", "172.*.*.*", "*.local"],
  partialPrefetching: true,
  experimental: {
    // Форма подачи объявления отправляет фото: до 20 штук, каждое сжато примерно до 300 КБ.
    // По умолчанию серверные действия принимают только 1 МБ.
    serverActions: { bodySizeLimit: "40mb" },
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
