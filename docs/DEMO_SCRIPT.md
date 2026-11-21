# Keitaro Manager — сценарий скринкаста (≈ 2:50)

> Откройте этот файл рядом с экраном. Слева — что делать, справа/ниже — что говорить.
> Весь путь (кнопки, поля, цифры) проверен в реальном приложении: фронтенд → бэкенд → PostgreSQL.
> Keitaro при проверке был **эмулятором**; с реальным Keitaro названия офферов/доменов будут вашими, а цифры долей — те же.

---

## 0. Выбор режима — решите ДО записи

| Режим | Когда | Что сказать в видео |
|-------|-------|---------------------|
| **A. Реальный Keitaro** (рекомендуется) | у вас есть доступ к Keitaro из ТЗ (URL + API-ключ из админки) | «Connected to a real Keitaro instance» + в конце показать созданную кампанию в админке Keitaro |
| **B. Эмулятор** | доступа к Keitaro нет | Обязательно плашка **«Mock Keitaro API (test emulator)»** на всё видео и фраза в начале. Офферы называются Offer A/B/C, домен `track.example.com` — это видно и честно |

Не выдавайте режим B за реальную интеграцию.

---

## 1. Подготовка (за 10 минут до записи, НЕ в кадре)

1. Запуск:
   ```bash
   cp .env.example .env        # заполнить SECRET_KEY, POSTGRES_PASSWORD, ADMIN_PASSWORD
   docker compose up -d --build
   docker compose ps           # все 3 сервиса healthy
   ```
   **Только для режима B** — в `.env` дополнительно `KEITARO_ALLOW_HTTP=true` и `KEITARO_ALLOW_PRIVATE_HOSTS=true`,
   затем `docker compose up -d`, и в отдельном терминале запустить эмулятор:
   ```bash
   docker run --rm -p 9100:9100 -v "$PWD/backend:/app" -w /app python:3.13-slim \
     sh -c "pip install -q httpx uvicorn && python scripts/mock_keitaro.py"
   ```
   В Настройках тогда: URL `http://host.docker.internal:9100`, ключ `valid-key-0123456789`.
   Эмулятор хранит данные в памяти — не перезапускайте его между подготовкой и записью.
2. Открыть <http://localhost:8080>, войти, **Настройки** → ввести Keitaro API URL и API Key → **Проверить подключение**
   → «Подключение к Keitaro успешно» → **Сохранить**. Затем **Выйти** (чтобы запись началась с экрана входа).
3. Создать заранее «существующую» кампанию (для сцены 6): **Создать кампанию** → Name `Existing DE campaign`,
   GEO `DE`, любой оффер, домен, группа, источник → **Create Campaign**. В ней должен быть **ровно 1 оффер на 100 %**.
4. Определить для записи 3 оффера: основной (Offer A) и ещё два для добавления (Offer B, Offer C).
5. Браузер: отдельное окно/профиль без закладок и расширений, одна вкладка (+ вкладка админки Keitaro в режиме A,
   уже залогиненная и открытая на списке кампаний). Масштаб страницы **90 %** (Cmd + −), чтобы карточка офферов была
   видна без прокрутки. Разрешение записи 1920×1080 или окно ~1600×1000.
6. macOS: включить «Не беспокоить», закрыть мессенджеры, спрятать Dock, убрать с рабочего стола лишнее.
7. В терминале для сцены 1 заранее набрать `docker compose ps` (не нажимать Enter) и сделать `clear`.
   Убедиться, что в истории/на экране нет `.env`, ключей и паролей.

---

## 2. Сценарий с таймингом

### Сцена 1 · 0:00–0:12 · Запуск
| Действие | Подпись на экране |
|----------|------------------|
| Терминал: Enter на `docker compose ps` — видны `db`, `backend`, `frontend` в статусе **healthy**. | **Keitaro Manager — FastAPI + React + PostgreSQL** |

> 🎙 *"Hi! This is Keitaro Manager — a FastAPI and React wrapper around the Keitaro Admin API. It runs in Docker: PostgreSQL, the backend and the frontend, all healthy."*
>
> Режим B — добавить: *"Today it's connected to a local Keitaro API emulator, because I don't have a live tracker here."*

### Сцена 2 · 0:12–0:25 · Вход
| Действие | Подпись |
|----------|---------|
| Браузер → `localhost:8080` → открывается **страница входа**. Логин `admin`, пароль (точки), **Войти**. | **Every API endpoint requires login** |

> 🎙 *"The whole API is behind authentication — passwords are hashed, and repeated failed logins are locked out."*

### Сцена 3 · 0:25–0:40 · Интерфейс
| Действие | Подпись |
|----------|---------|
| Открылась страница **Кампании**: список, поиск, фильтры. Навести курсор на индикатор слева внизу **«Keitaro подключён»**. Быстро кликнуть **Ресурсы** (домены/группы/источники/офферы из Keitaro) и вернуться в **Кампании**. | **Live data from Keitaro** |

> 🎙 *"The dashboard reads campaigns straight from Keitaro. The API key is stored encrypted and is never sent back to the browser. Here are the domains, groups, traffic sources and offers — also pulled from Keitaro."*

### Сцена 4 · 0:40–1:15 · Создание кампании
| Действие | Подпись |
|----------|---------|
| Слева **Создать кампанию**. | **Part 1 — Campaign Creator** |
| **Campaign Name**: `Demo | US | Offer A` | |
| **Country / GEO**: `US` | |
| **Offer ID**: выбрать основной оффер (`#10 — Offer A`) | |
| **Domain**, **Group**, **Traffic Source**: выбрать по одному значению | |
| Навести курсор на карточку справа **«Схема потоков»**: Поток 1 · Redirect → страна US → google.com; Поток 2 · Offers → остальные → оффер 100 %. | **Stream 1: US → Google · Stream 2: everyone else → offer** |
| Нажать **Create Campaign** → тост «Кампания … создана (#ID)», открывается редактор кампании. | |

> 🎙 *"Part one — the campaign creator. I enter a name, the GEO and the offer, and pick the domain, group and traffic source from Keitaro. The preview shows what will be created: visitors from the US go to Google, everyone else goes to the offer. Before writing anything, the backend checks that all four objects exist in Keitaro, and if any step fails, everything already created is rolled back."*

### Сцена 5 · 1:15–1:40 · Два потока
| Действие | Подпись |
|----------|---------|
| В шапке кампании нажать **Потоки (2)**. | **Two streams, evaluated top to bottom** |
| Навести на поток **1 · GEO Redirect** — «Страна = US», «Редирект на URL … https://www.google.com». | |
| Навести на поток **2 · Offers** — «Все пользователи», оффер **100 %**. | |

> 🎙 *"Here are the two streams. The campaign uses position rotation, so Keitaro checks streams from top to bottom: stream one catches US visitors and redirects them to Google; stream two has no filters, so it takes everyone else and sends them to the offer at one hundred percent."*

**Только режим A, +10 с (1:40–1:50):** переключиться на вкладку админки Keitaro → обновить список кампаний →
показать `Demo | US | Offer A` и её два потока. Подпись: **Same campaign inside Keitaro**.
> 🎙 *"And this is the same campaign inside Keitaro itself."*

### Сцена 6 · 1:50–2:35 · Редактор: офферы и распределение трафика
| Действие | Подпись |
|----------|---------|
| **Кампании** → кликнуть **Existing DE campaign**. Карточка **«Офферы и распределение трафика»**: 1 оффер, 100 %. | **Part 2 — Campaign Editor** |
| В **«Выберите оффер для добавления»** выбрать Offer B, поле доли пустое → **Добавить оффер** → **50 % / 50 %**. | **Add offer → equal split** |
| Выбрать Offer C, в поле **«Доля, % (авто)»** ввести `20` → **Добавить оффер** → **40 / 40 / 20**. | **Fixed 20 %, others rescaled** |
| В первой строке ввести `60` → внизу красным «Итого по активным: 120 % … лишние 20 %», кнопка **Сохранить распределение** неактивна. | **Total must be exactly 100 %** |
| Нажать **Пересчитать до 100%** → **50 / 33 / 17**, итог зелёный. Нажать **Сохранить распределение** → тост «сохранено». | **Normalize → Save** |
| У Offer C нажать 🗑 **Удалить оффер** → в диалоге **Удалить** → **60 / 40**. | **Remove → remaining offers rebalance** |

> 🎙 *"Part two — the editor for an existing campaign. I add a second offer: traffic is split fifty-fifty. I add a third one with a fixed twenty percent — the others are rescaled to forty and forty. If I type sixty here, the total is a hundred and twenty, and saving is blocked: active offers must always add up to exactly one hundred percent — the backend checks this again before anything is sent to Keitaro. 'Normalize' fixes it to fifty, thirty-three, seventeen, and I save. Finally I remove an offer, confirm, and the remaining two are rebalanced to sixty-forty."*

### Сцена 7 · 2:35–2:50 · Журнал и финал
| Действие | Подпись |
|----------|---------|
| Слева **Журнал** — все операции: создание кампании, добавление/удаление офферов, со статусом и пользователем. | **Every change is audited** |
| Остановиться на странице 2 секунды. | **github.com/Islam0122/keitaro-manager** |

> 🎙 *"Every write to Keitaro is logged with its status and the user who made it. The code, the tests and the setup guide are in the GitHub repository. Thanks for watching!"*

Итог: ~2:40 в режиме B, ~2:50 в режиме A.

---

## 3. Что показать обязательно / что можно пропустить

**Обязательно (требования ТЗ):**
- Создание кампании: название, GEO, оффер, домен/группа/источник → **Create Campaign**.
- Экран **Потоки**: GEO Redirect (страна → google.com) и Offers (остальные → оффер 100 %).
- Открытие существующей кампании, **добавление** и **удаление** оффера.
- Цифры распределения: 50/50 → 40/40/20 → блокировка при 120 % → нормализация → 60/40 после удаления.
- В режиме A — кампания в админке Keitaro (самое сильное доказательство реальной интеграции).

**Если время поджимает — пропустить:**
- Страницу **Ресурсы** (сцена 3), страницу **Журнал** (сцена 7 — оставить только финальную фразу).
- Кнопку **Поровну**, выключение оффера тумблером.

**Не показывать в этом видео:**
- **Настройки** — там виден URL трекера; ключ замаскирован, но страница не нужна.
- Редактирование/создание потоков вручную, остановку/удаление кампании, смену пароля — функции есть, но не влезут в 3 минуты.
- Сценарий отката при ошибке — он покрыт автотестами; в живом видео его честно не воспроизвести без поломки Keitaro.
  Достаточно фразы в сцене 4.
- Код, `.env`, терминал с переменными окружения, OpenAPI с токеном.

---

## 4. Все подписи (для монтажа, по порядку)

| Время | Подпись |
|-------|---------|
| 0:00 | Keitaro Manager — FastAPI + React + PostgreSQL |
| 0:00 (режим B, на всё видео, в углу) | Mock Keitaro API (test emulator) |
| 0:12 | Every API endpoint requires login |
| 0:25 | Live data from Keitaro |
| 0:40 | Part 1 — Campaign Creator |
| 0:58 | Stream 1: US → Google · Stream 2: everyone else → offer |
| 1:15 | Two streams, evaluated top to bottom |
| 1:40 (режим A) | Same campaign inside Keitaro |
| 1:50 | Part 2 — Campaign Editor |
| 1:58 | Add offer → equal split |
| 2:05 | Fixed 20 %, others rescaled |
| 2:12 | Total must be exactly 100 % |
| 2:20 | Normalize → Save |
| 2:28 | Remove → remaining offers rebalance |
| 2:35 | Every change is audited |
| 2:45 | github.com/Islam0122/keitaro-manager |

Стиль: белый текст на полупрозрачной тёмной плашке внизу по центру, 1–2 строки, 3–4 секунды каждая.

---

## 5. Запись экрана на macOS

### Вариант 1 — QuickTime Player / Cmd + Shift + 5 (проще)
1. Нажать **Cmd + Shift + 5** → «Записать выбранную часть экрана» → обвести окно браузера (терминал положить рядом
   или переключаться на весь экран).
2. **Параметры**: Микрофон — встроенный или внешний; «Показывать нажатия мышью» — **вкл**; таймер 5 с.
3. **Записать** → пройти сценарий → остановить кнопкой ⏹ в строке меню.
4. Файл `.mov` появится на рабочем столе. Обрезка: открыть в QuickTime → **Правка → Обрезать** (Cmd + T).
5. Подписи QuickTime не делает — добавить в **iMovie** (Титры → «Нижняя треть») или CapCut, экспорт 1080p.

### Вариант 2 — OBS Studio (больше контроля)
1. **Настройки → Видео**: базовое и выходное разрешение 1920×1080, 30 FPS.
2. **Настройки → Вывод**: Режим «Простой», формат **mp4** (или mkv + «Файл → Ремукс в mp4»), качество «Высокое».
3. **Источники** → «+» → **Захват экрана macOS** (выбрать дисплей или окно браузера) + **Захват входного аудио** (микрофон).
   При первом запуске разрешить OBS доступ к записи экрана и микрофону в «Системные настройки → Конфиденциальность».
4. Плашку «Mock Keitaro API (test emulator)» (режим B) можно сразу добавить источником **Текст** — она будет в кадре всё видео.
5. Проверить уровень микрофона (зелёная/жёлтая зона), записать 10 с теста и прослушать.
6. **Начать запись** → сценарий → **Остановить запись**. Файл в `~/Movies`.

Советы: говорите спокойно, делайте паузу 0,5 с после каждого клика; курсором показывайте то, о чём говорите;
если сбились — сделайте паузу 2 с и повторите фразу, лишнее вырежете при монтаже.

---

## 6. Финальный чек-лист перед отправкой

**Безопасность**
- [ ] Ни в одном кадре нет `.env`, API-ключа, пароля (поле пароля только точками), токена, URL админки с логином.
- [ ] Страница **Настройки** не показана (или URL трекера на ней размыт).
- [ ] Нет уведомлений, почты, мессенджеров, личных вкладок и закладок.

**Честность**
- [ ] Режим B: плашка «Mock Keitaro API (test emulator)» видна всё видео и это сказано голосом в начале.
- [ ] Режим A: показана та же кампания в админке Keitaro.
- [ ] Не прозвучало ничего, чего не было на экране.

**Содержание**
- [ ] Создание кампании: название, GEO, оффер, домен, группа, источник.
- [ ] Видны оба потока: GEO Redirect (страна → google.com) и Offers (оффер 100 %).
- [ ] Добавление оффера, удаление оффера с подтверждением.
- [ ] Цифры на экране: 50/50 → 40/40/20 → 120 % блокирует сохранение → 50/33/17 → 60/40.
- [ ] Длительность ≤ 3:00.

**Качество**
- [ ] 1080p, текст в браузере читается, звук без шума и щелчков, громкость ровная.
- [ ] Подписи не перекрывают важные цифры (карточка офферов — в центре/внизу экрана; при необходимости поднимите подписи наверх).
- [ ] Видео загружено (YouTube «по ссылке» / Google Drive с доступом «у кого есть ссылка») и ссылка открывается в режиме инкогнито.
- [ ] В README или в сообщении проверяющему — ссылка на видео и на репозиторий.

**После записи**
- [ ] Режим A: созданные тестовые кампании удалить (кнопка **Удалить** в редакторе → кампания уходит в архив Keitaro).
- [ ] Режим B: вернуть в `.env` `KEITARO_ALLOW_HTTP=false`, `KEITARO_ALLOW_PRIVATE_HOSTS=false`, остановить эмулятор.
