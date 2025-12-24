# Nexus - План реализации

**Проект:** Десктопное приложение для автоматизации Telegram
**Стек:** Electron + Vue 3 + Python (Telethon)

---

## Исходный проект (база для копирования)

**Путь:** `/Users/fyodorlukashov/Music/GramGPT`

### Что копировать:

**Frontend (Vue компоненты):**
```
GramGPT/Frontend/pages/panel/modules/
├── mass-react.vue         → Автолайки
├── neuro-commenting.vue   → Автокомменты
├── accounts/              → Менеджер аккаунтов
└── warming.vue            → Прогрев (бонус)

GramGPT/Frontend/stores/
├── useModuleExecutor.ts   → Логика выполнения
└── useAccountViewerStore.ts

GramGPT/Frontend/composables/
└── (все нужные)
```

**Backend (Python):**
```
GramGPT/Backend/backend/apps/telegram_accounts/
├── models.py              → TelegramAccount, Proxy

GramGPT/Backend/backend/worker/executors/handlers/
├── react_handler.py       → Лайки
├── neuro_handler.py       → Комменты
├── account_handler.py     → Управление аккаунтами
└── base_handler.py        → Базовый класс
```

### Что адаптировать:
- Django ORM → SQLAlchemy + SQLite
- Redis Streams → asyncio Queue
- REST API → FastAPI
- WebSocket → Electron IPC

---

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│                  Nexus Desktop App                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────┐      ┌───────────────────┐   │
│  │    Vue 3 UI      │◄────►│   Electron Main   │   │
│  │   (Renderer)     │ IPC  │    (Node.js)      │   │
│  │                  │      │                   │   │
│  │  - PrimeVue      │      │  - Window mgmt    │   │
│  │  - Tailwind      │      │  - IPC handlers   │   │
│  │  - Pinia         │      │  - Auto-updater   │   │
│  └──────────────────┘      └─────────┬─────────┘   │
│                                      │             │
│                              spawn / HTTP          │
│                                      │             │
│                            ┌─────────▼─────────┐   │
│                            │   Python Backend  │   │
│                            │                   │   │
│                            │  - FastAPI        │   │
│                            │  - Telethon       │   │
│                            │  - SQLite         │   │
│                            │  - Task Queue     │   │
│                            └───────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Этап 1: Фундамент (5-7 дней)

### 1.1 Инициализация проекта (1 день)
- [ ] Создать Electron + Vue 3 проект (electron-vite)
- [ ] Настроить TypeScript
- [ ] Настроить ESLint + Prettier
- [ ] Настроить electron-builder для сборки

### 1.2 Python Backend (2 дня)
- [ ] Создать FastAPI приложение
- [ ] Настроить SQLite + Alembic миграции
- [ ] Модель TelegramAccount (из GramGPT)
- [ ] Модель Proxy
- [ ] Модель AccountGroup
- [ ] Модель AccountTag
- [ ] API endpoints: CRUD аккаунтов и прокси

### 1.3 Интеграция Electron + Python (1 день)
- [ ] Spawn Python процесса из Electron
- [ ] IPC bridge для коммуникации
- [ ] Health check Python backend
- [ ] Graceful shutdown

### 1.4 Импорт аккаунтов (2 дня)
- [ ] Импорт tdata (парсинг формата Telegram Desktop)
- [ ] Импорт JSON сессий (Telethon/Pyrogram)
- [ ] Ручное добавление (phone + код)
- [ ] Валидация сессий через Telethon
- [ ] UI формы импорта

### 1.5 Управление прокси (1 день)
- [ ] CRUD прокси (SOCKS5, HTTP)
- [ ] Валидация прокси при добавлении
- [ ] Привязка прокси к аккаунтам
- [ ] UI таблицы прокси

**Результат этапа:** Можно добавлять аккаунты и прокси, базовая инфраструктура работает.

---

## Этап 2: Менеджер аккаунтов (6-8 дней)

### 2.1 Таблица аккаунтов (2 дня)
- [ ] Виртуализированная таблица (AG Grid или TanStack)
- [ ] Колонки: ID, Username, Phone, Status, Proxy, Group, Tags
- [ ] Сортировка по всем колонкам
- [ ] Фильтрация по статусу, группе, тегам
- [ ] Поиск по username/phone
- [ ] Пагинация

### 2.2 Группы аккаунтов (1.5 дня)
- [ ] CRUD групп
- [ ] Перемещение аккаунтов между группами
- [ ] Drag-n-drop (опционально)
- [ ] Sidebar с деревом групп

### 2.3 Система тегов (1 день)
- [ ] CRUD тегов (название + цвет)
- [ ] Назначение тегов аккаунтам (many-to-many)
- [ ] Фильтрация по тегам
- [ ] UI: цветные badges

### 2.4 Массовые действия (1.5 дня)
- [ ] Множественный выбор (чекбоксы)
- [ ] Массовое удаление
- [ ] Массовое перемещение в группу
- [ ] Массовое назначение прокси
- [ ] Массовая проверка статуса

### 2.5 Статусы и мониторинг (2 дня)
- [ ] Отображение статуса (valid, banned, spamblock и т.д.)
- [ ] Цветовая индикация
- [ ] Фоновая проверка статусов
- [ ] Live-обновление статусов в таблице
- [ ] Детальная информация при клике

**Результат этапа:** Полноценный менеджер аккаунтов как в Teleraptor.

---

## Этап 3: Модуль Автолайки (5-7 дней)

### 3.1 Форма создания задания (1.5 дня)
- [ ] Выбор канала/поста (по ссылке или username)
- [ ] Выбор типа реакции (👍❤️🔥 и т.д.)
- [ ] Количество лайков
- [ ] Задержка между лайками (мин/макс)
- [ ] Режим: на конкретный пост / на новые посты

### 3.2 Выбор аккаунтов (1 день)
- [ ] По группе
- [ ] По тегам
- [ ] По статусу (только valid)
- [ ] Случайные N из пула
- [ ] Исключение определенных аккаунтов

### 3.3 Выполнение заданий (2 дня)
- [ ] Task queue (asyncio)
- [ ] Параллельное выполнение (configurable concurrency)
- [ ] Retry при ошибках
- [ ] Обработка FloodWait
- [ ] Прогресс в реальном времени
- [ ] Отмена задания

### 3.4 Журнал выполнения (1.5 дня)
- [ ] Таблица истории заданий
- [ ] Статус: pending, running, completed, failed
- [ ] Детали: время, пост, реакция, успех/ошибки
- [ ] Логи ошибок (expandable)
- [ ] Экспорт в CSV

**Результат этапа:** Рабочий модуль автолайков с журналом.

---

## Этап 4: Модуль Автокомменты (8-11 дней)

### 4.1 Подписка на каналы (2 дня)
- [ ] Автоматическое вступление в каналы
- [ ] Список целевых каналов
- [ ] Проверка возможности комментирования
- [ ] Обработка ограничений (private, request to join)

### 4.2 Мониторинг новых постов (2 дня)
- [ ] Подключение к каналам через Telethon
- [ ] Обнаружение новых постов
- [ ] Фильтрация постов (по ключевым словам, типу контента)
- [ ] Очередь постов для комментирования

### 4.3 Генерация комментариев (1.5 дня)
- [ ] Шаблоны комментариев
- [ ] Спинтакс ({Привет|Здравствуйте})
- [ ] Подстановка переменных
- [ ] (Опционально) AI генерация

### 4.4 Логика комментирования (2 дня)
- [ ] Режим: рандомный аккаунт
- [ ] Режим: последовательно (round-robin)
- [ ] Режим: по приоритету (warmed first)
- [ ] Задержки между комментариями
- [ ] Антиспам: лимит комментов на аккаунт

### 4.5 Форма задания + Журнал (2.5 дня)
- [ ] UI создания задания
- [ ] Параметры по умолчанию (autofill)
- [ ] Журнал выполненных комментариев
- [ ] Статистика: успешных/неудачных
- [ ] Логи ошибок

**Результат этапа:** Полный функционал автокомментов.

---

## Структура проекта

```
Nexus/
├── electron/
│   ├── main.ts                 # Electron main process
│   ├── preload.ts              # IPC bridge
│   └── python-bridge.ts        # Python process management
│
├── src/                        # Vue 3 приложение
│   ├── assets/
│   ├── components/
│   │   ├── accounts/           # Таблица, формы аккаунтов
│   │   ├── proxy/              # Управление прокси
│   │   ├── tasks/              # Компоненты заданий
│   │   └── common/             # Общие UI компоненты
│   ├── layouts/
│   ├── pages/
│   │   ├── Dashboard.vue
│   │   ├── Accounts.vue
│   │   ├── Proxy.vue
│   │   ├── AutoLikes.vue
│   │   ├── AutoComments.vue
│   │   └── Settings.vue
│   ├── stores/
│   │   ├── useAccountStore.ts
│   │   ├── useProxyStore.ts
│   │   ├── useTaskStore.ts
│   │   └── useSettingsStore.ts
│   ├── composables/
│   ├── types/
│   ├── App.vue
│   └── main.ts
│
├── backend/                    # Python backend
│   ├── api/
│   │   ├── accounts.py
│   │   ├── proxy.py
│   │   ├── tasks.py
│   │   └── router.py
│   ├── database/
│   │   ├── models.py
│   │   ├── database.py
│   │   └── migrations/
│   ├── telegram/
│   │   ├── client.py
│   │   ├── session_manager.py
│   │   └── importers/
│   │       ├── tdata.py
│   │       └── json_session.py
│   ├── workers/
│   │   ├── queue.py
│   │   ├── likes_worker.py
│   │   └── comments_worker.py
│   ├── main.py                 # FastAPI entrypoint
│   └── requirements.txt
│
├── resources/
│   ├── icons/
│   └── python/                 # Embedded Python (PyInstaller)
│
├── electron-builder.yml
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## Технологии

### Frontend
| Технология | Версия | Назначение |
|------------|--------|------------|
| Electron | 33+ | Desktop runtime |
| Vue 3 | 3.5+ | UI framework |
| TypeScript | 5.0+ | Type safety |
| Vite | 6.0+ | Build tool |
| PrimeVue | 4.0+ | UI components |
| Tailwind CSS | 3.4+ | Styling |
| Pinia | 2.2+ | State management |
| AG Grid | 32+ | Data tables |

### Backend
| Технология | Версия | Назначение |
|------------|--------|------------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.115+ | API framework |
| Telethon | 1.37+ | Telegram MTProto |
| SQLite | 3.40+ | Database |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.14+ | Migrations |
| Pydantic | 2.0+ | Validation |

### Build & Deploy
| Технология | Назначение |
|------------|------------|
| electron-vite | Fast build |
| electron-builder | Packaging (.exe, .dmg) |
| electron-updater | Auto-updates |
| PyInstaller | Python bundling |

---

## API Endpoints (Backend)

### Accounts
```
GET    /api/accounts              # Список аккаунтов
POST   /api/accounts              # Создать аккаунт
GET    /api/accounts/{id}         # Получить аккаунт
PUT    /api/accounts/{id}         # Обновить аккаунт
DELETE /api/accounts/{id}         # Удалить аккаунт
POST   /api/accounts/import/tdata # Импорт tdata
POST   /api/accounts/import/json  # Импорт JSON
POST   /api/accounts/check        # Проверить статус
POST   /api/accounts/bulk-action  # Массовое действие
```

### Proxy
```
GET    /api/proxy                 # Список прокси
POST   /api/proxy                 # Создать прокси
PUT    /api/proxy/{id}            # Обновить прокси
DELETE /api/proxy/{id}            # Удалить прокси
POST   /api/proxy/{id}/validate   # Проверить прокси
```

### Groups & Tags
```
GET    /api/groups                # Список групп
POST   /api/groups                # Создать группу
PUT    /api/groups/{id}           # Обновить группу
DELETE /api/groups/{id}           # Удалить группу

GET    /api/tags                  # Список тегов
POST   /api/tags                  # Создать тег
DELETE /api/tags/{id}             # Удалить тег
```

### Tasks
```
GET    /api/tasks                 # Список заданий
POST   /api/tasks/likes           # Создать задание лайков
POST   /api/tasks/comments        # Создать задание комментов
GET    /api/tasks/{id}            # Статус задания
DELETE /api/tasks/{id}            # Отменить задание
GET    /api/tasks/{id}/logs       # Логи задания
```

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Telegram API изменения | Средняя | Абстракция клиента, быстрое обновление |
| FloodWait баны | Высокая | Умные задержки, очередь, прогрев |
| Проблемы с tdata импортом | Средняя | Fallback на ручной вход |
| Размер приложения (Python) | Низкая | PyInstaller оптимизация |
| Кроссплатформенность | Средняя | Тестирование на Win/Mac/Linux |

---

## Milestone Checkpoints

### После Этапа 1:
- [ ] Приложение запускается
- [ ] Можно добавить аккаунт (любым способом)
- [ ] Можно добавить и привязать прокси
- [ ] Аккаунт подключается к Telegram

### После Этапа 2:
- [ ] Таблица аккаунтов с фильтрами работает
- [ ] Группы и теги функционируют
- [ ] Массовые действия работают
- [ ] Статусы обновляются

### После Этапа 3:
- [ ] Можно создать задание на лайки
- [ ] Лайки ставятся успешно
- [ ] Журнал показывает результаты
- [ ] Прогресс отображается в реальном времени

### После Этапа 4:
- [ ] Аккаунты подписываются на каналы
- [ ] Новые посты обнаруживаются
- [ ] Комментарии отправляются
- [ ] Журнал и статистика работают

---

## Следующие шаги

1. Утвердить план с заказчиком
2. Получить предоплату за Этап 1
3. Инициализировать проект
4. Начать разработку

---

*Создано: 24.12.2024*
*Версия: 1.0*
