// POST /api/upload-doc?personId=<id>&filename=<name>&title=<title> — загрузка документа.
// Тело запроса — «сырые» байты файла (изображение или PDF).
// Файл кладётся в Blob (media/docs/<unique>.<ext>), URL дописывается в person.documents[].
import { put } from '@vercel/blob';
import { cors, readData, writeData, readRawBody, uniqueName } from '../lib/store.js';

export default async function handler(req, res) {
  cors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' });
  try {
    const url = new URL(req.url, 'http://x');
    const personId = url.searchParams.get('personId') || '';
    const filename = url.searchParams.get('filename') || 'doc.jpg';
    const title = url.searchParams.get('title') || filename;
    let ext = (filename.match(/\.[a-z0-9]+$/i) || ['.jpg'])[0].toLowerCase();
    if (!['.jpg', '.jpeg', '.png', '.webp', '.gif', '.pdf'].includes(ext)) ext = '.jpg';

    const buf = await readRawBody(req);
    if (!buf.length) return res.status(400).json({ error: 'no file' });

    const blob = await put('media/docs/' + uniqueName(ext), buf, {
      access: 'public',
      addRandomSuffix: false,
      contentType: req.headers['content-type'] || 'application/octet-stream',
    });

    if (personId) {
      const data = (await readData()) || {};
      const p = data.individuals && data.individuals[personId];
      if (p) {
        if (!Array.isArray(p.documents)) p.documents = [];
        p.documents.push({ file: blob.url, title });
        await writeData(data);
      }
    }

    return res.status(200).json({ url: blob.url, filename: blob.url });
  } catch (e) {
    return res.status(500).json({ error: String(e) });
  }
}
