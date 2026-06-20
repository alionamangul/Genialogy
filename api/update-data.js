// POST /api/update-data — сохраняет весь data.json в Vercel Blob.
// Тело запроса — JSON со всей структурой данных (как держит её фронтенд в памяти).
import { cors, writeData } from '../lib/store.js';

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' });
  try {
    // Vercel парсит application/json в req.body автоматически
    const data = req.body && typeof req.body === 'object' ? req.body : null;
    if (!data || !data.individuals) {
      return res.status(400).json({ error: 'invalid data' });
    }
    await writeData(data);
    return res.status(200).json({ ok: true });
  } catch (e) {
    return res.status(500).json({ error: String(e) });
  }
}
