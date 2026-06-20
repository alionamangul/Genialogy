# Архитектура

> Как устроен проект технически. Схемы в формате Mermaid — GitHub рендерит их автоматически.
> Последнее обновление: 2026-06-20

## Обзор

Проект — статический фронтенд (один HTML-файл) плюс тонкий бэкенд из serverless-функций.
Никакой базы данных: источник истины — файл `data.json` в репозитории, медиа — в Vercel Blob.

## Компоненты системы

```mermaid
graph TB
    subgraph client["🖥️ Браузер (клиент)"]
        HTML["index.html<br/>HTML + CSS + JS в одном файле"]
        Tabs["Вкладки: Дерево · Список · Медиа<br/>Документы · История · Факты · География · Книга"]
        Layout["Движок раскладки дерева<br/>renderFocusedTree / placeUp / placeDown"]
        HTML --> Tabs
        HTML --> Layout
    end

    subgraph vercel["☁️ Vercel (прод)"]
        Static["Статика<br/>index.html, media/"]
        API["Python serverless<br/>api/update-data.py<br/>api/upload-photo.py<br/>api/upload-doc.py"]
        Blob[("Vercel Blob<br/>фото и документы")]
    end

    subgraph github["🐙 GitHub"]
        Repo["alionamangul/Genialogy<br/>data.json — источник истины"]
    end

    subgraph local["💻 Локальная разработка"]
        Serve["serve.py :8081<br/>отдаёт /tmp/family-tree"]
    end

    HTML -->|"GET сайт"| Static
    HTML -->|"POST /api/*"| API
    API -->|"коммит data.json"| Repo
    API -->|"PUT файл"| Blob
    HTML -->|"картинки по URL"| Blob
    Static -.->|"деплой при push"| Repo
    HTML -.->|"локально"| Serve
    Serve -->|"пишет"| Repo
```

## Поток: сохранение карточки человека

```mermaid
sequenceDiagram
    participant U as Пользователь
    participant JS as index.html (JS)
    participant API as api/update-data.py
    participant GH as GitHub API

    U->>JS: правит поле в карточке
    Note over JS: debounce 800 мс<br/>(+ flush при закрытии)
    JS->>JS: обновляет объект DATA в памяти
    JS->>API: POST /api/update-data (весь data.json)
    API->>GH: GET contents/data.json (берём sha)
    API->>GH: PUT contents/data.json (новый коммит)
    GH-->>API: 200 OK
    API-->>JS: { ok: true }
    Note over GH: Vercel ловит push<br/>и передеплоивает сайт
```

## Поток: загрузка фотографии

```mermaid
sequenceDiagram
    participant U as Пользователь
    participant JS as index.html (JS)
    participant API as api/upload-photo.py
    participant Blob as Vercel Blob
    participant GH as GitHub API

    U->>JS: выбирает фото с устройства
    JS->>JS: сжатие до 1600px (canvas)
    JS->>API: POST /api/upload-photo (multipart)
    API->>Blob: PUT media/<id>.jpg
    Blob-->>API: { url }
    API->>GH: дописывает url в photoIds[] и коммитит data.json
    API-->>JS: { url }
    JS->>JS: добавляет url в DATA, перерисовывает галерею
    JS->>Blob: GET <url> (показ фото)
```

## Логика выбора пути к медиа

```mermaid
flowchart LR
    Ref["ссылка из data.json"] --> Q{"начинается с<br/>http или / ?"}
    Q -->|да| Direct["использовать как есть<br/>(Vercel Blob URL)"]
    Q -->|нет| Build["./media/&lt;ref&gt;.jpg<br/>(старое фото в репозитории)"]
```

Реализовано хелперами `photoUrl()` и `docUrl()` в `index.html`. Благодаря этому старые
фото (числовые id) и новые (полные URL) работают одновременно без миграции данных.

## Движок раскладки дерева

Самая сложная часть `index.html` — расчёт координат узлов. Конвейер:

```
renderFocusedTree
  ├─ getAncestorChain / walkAncestors   — собрать видимых предков обеих ветвей
  ├─ assignGenerations                  — пронумеровать поколения
  ├─ placeDown                          — разместить потомков сверху вниз
  ├─ placeUp                            — разместить предков снизу вверх (с guard от рекурсии)
  ├─ resolveRowOverlaps / resolveOverlaps — развести пересечения, пары как единое целое
  ├─ Step F / Step G                    — финальное центрирование родителей над детьми
  └─ нормализация + центрирование верхнего ряда
```

Ключевые константы: `NODE_W=100`, `NODE_H=90`, `SPOUSE_GAP=8`, `H_GAP=20`, `V_GAP=80`.

> Известная проблема раскладки (предки не строго над ребёнком при конфликте веток)
> описана в [BACKLOG.md](BACKLOG.md).

## Конфигурация окружения (Vercel)

| Переменная | Назначение | Откуда |
|---|---|---|
| `GITHUB_TOKEN` | запись `data.json` в репозиторий | GitHub → Settings → Tokens (scope `repo`) |
| `BLOB_READ_WRITE_TOKEN` | загрузка медиа в Blob | добавляется при подключении Vercel Blob |

## Почему так (ключевые решения)

- **Один HTML-файл** — простота: нет сборки, можно открыть и отредактировать что угодно.
- **`data.json` в git вместо БД** — версионирование «бесплатно», вся история правок в коммитах.
- **Vercel Blob для медиа** — git не предназначен для бинарников; Blob отдаёт через CDN.
- **GitHub API для записи** — прод не имеет файловой системы для постоянного хранения,
  поэтому данные коммитятся обратно в репозиторий.
