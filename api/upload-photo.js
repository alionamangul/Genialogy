// POST /api/upload-photo?personId=<id>&filename=<name> — загрузка фото.
// Тело запроса — «сырые» байты файла (Content-Type: image/*).
// Файл кладётся в Blob (media/<unique>.<ext>), его URL дописывается в person.photoIds[].
import { put } from '@vercel/blob';
import { cors, readData, writeData, readRawBody, uniqueName } from '../lib/store.js';

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' });
  try {
    const url = new URL(req.url, 'http://x');
    const personId = url.searchParams.get('personId') || '';
    const filename = url.searchParams.get('filename') || 'photo.jpg';
    let ext = (filename.match(/\.[a-z0-9]+$/i) || ['.jpg'])[0].toLowerCase();
    if (!['.jpg', '.jpeg', '.png', '.webp', '.gif'].includes(ext)) ext = '.jpg';

    const buf = await readRawBody(req);
    if (!buf.length) return res.status(400).json({ error: 'no file' });

    const blob = await put('media/' + uniqueName(ext), buf, {
      access: 'public',
      addRandomSuffix: false,
      contentType: req.headers['content-type'] || 'image/jpeg',
    });

    if (personId) {
      const data = (await readData()) || {};
      const p = data.individuals && data.individuals[personId];
      if (p) {
        if (!Array.isArray(p.photoIds)) p.photoIds = [];
        p.photoIds.push(blob.url);
        await writeData(data);
      }
    }

    return res.status(200).json({ url: blob.url, photoId: blob.url });
  } catch (e) {
    return res.status(500).json({ error: String(e) });
  }
}
