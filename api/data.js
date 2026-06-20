// GET /api/data — отдаёт актуальный data.json из Vercel Blob.
// Если в Blob его ещё нет (до первого сохранения) или Blob не подключён —
// возвращает 404, и фронтенд подхватывает исходный data.json из репозитория.
import { cors, readData } from '../lib/store.js';

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();
  try {
    const data = await readData();
    if (!data) return res.status(404).json({ error: 'no data in blob yet' });
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).send(JSON.stringify(data));
  } catch (e) {
    // Blob не подключён / ошибка — пусть фронтенд читает ./data.json из репозитория
    return res.status(404).json({ error: String(e) });
  }
}
