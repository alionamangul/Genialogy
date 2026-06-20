// Общая логика хранения данных в Vercel Blob.
// data.json лежит в Blob по фиксированному пути и перезаписывается при каждом сохранении.
// Медиа (фото, документы) — отдельные объекты в Blob, в data.json пишутся их полные URL.
import { put, list } from '@vercel/blob';

const DATA_PATH = 'data.json';

// CORS-заголовки для всех ответов API
export function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

// Прочитать data.json из Blob. Возвращает объект или null, если в Blob его ещё нет
// (тогда фронтенд сам подхватит исходный data.json из репозитория как «семя»).
export async function readData() {
  const { blobs } = await list({ prefix: DATA_PATH, limit: 100 });
  const exact = blobs.find((b) => b.pathname === DATA_PATH);
  if (!exact) return null;
  // cache-busting, чтобы не получить устаревшую версию из CDN
  const r = await fetch(exact.url + '?ts=' + Date.now(), { cache: 'no-store' });
  if (!r.ok) return null;
  return await r.json();
}

// Записать data.json в Blob (перезапись по фиксированному пути, без кеширования).
export async function writeData(data) {
  const body = JSON.stringify(data, null, 2);
  await put(DATA_PATH, body, {
    access: 'public',
    addRandomSuffix: false,
    allowOverwrite: true,
    contentType: 'application/json; charset=utf-8',
    cacheControlMaxAge: 0,
  });
}

// Прочитать «сырое» бинарное тело запроса (для загрузки файлов без multipart).
export async function readRawBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks);
}

// Сгенерировать уникальное имя файла без коллизий.
export function uniqueName(ext) {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8) + ext;
}
