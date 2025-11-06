# Mikrotik WireGuard Telegram Bot

Проект из двух сервисов для автоматизации управления WireGuard на MikroTik через Telegram:

1. **wg-transformer** — REST API для преобразования конфигураций WireGuard (генерация `.conf` и QR-кодов).  
2. **wg-telegram-bot** — Telegram-бот: создаёт peer на MikroTik через REST API, назначает IP из пула, генерирует и отправляет конфиг и QR.

---

## Возможности

- Создание нового WireGuard peer на MikroTik по команде из Telegram.  
- Автоматическая выдача IP-адресов из `WG_POOL` с учётом стартового адреса `WG_POOL_MIN`.  
- Генерация клиентского `.conf` и QR-кода.  
- Доступ ограничен по `ALLOWED_USER_ID`.  
- Отдельный REST-сервис для преобразования конфигов (wg-transformer), доступный по HTTP.

---

## Требования

- MikroTik RouterOS **7.1+** с включённым REST API (`/ip service enable www-ssl`, `/rest enable`).  
- Docker и docker-compose на хосте.  
- Telegram-бот, созданный через [@BotFather](https://t.me/BotFather).

---

## Установка

### 1. Клонирование репозитория
```bash
git clone git@github.com:Anzic23/Mikrotik-wg-bot.git
cd Mikrotik-wg-bot
```

### 2. Настройка окружения
В репозитории есть файл примера `.env.example`.  
Скопируйте его под именем `.env` и подставьте свои значения:

```bash
cp .env.example .env
nano .env
```

Пример содержимого:

```bash
TELEGRAM_BOT_TOKEN=8xxxxxxxxY
ALLOWED_USER_ID=2xxx3

MT_HOST=192.168.88.1
MT_PORT=443
MT_USER=wg-bot
MT_PASSWORD=SuperPass
MT_VERIFY_SSL=false

WG_INTERFACE=WG_Server
WG_POOL=192.168.220.0/24
WG_POOL_MIN=192.168.220.10
WG_DNS=192.168.220.1
WG_ENDPOINT=192.168.88.1:53254
WG_KEEPALIVE=16
WG_MTU=1280
```

---

### 3. Запуск
```bash
docker compose up -d --build
```

После запуска:
- `wg-transformer` слушает внутри контейнера на `8080` (проброшен наружу на `8647`);
- Telegram-бот автоматически подключается к REST API MikroTik.

---

## Использование бота

- `/start` — показать справку  
- `/newpeer` — создать нового peer (бот спросит имя и тип маршрутизации)  
- `/cancel` — отменить процесс создания

Бот создаёт peer на MikroTik, генерирует клиентский `.conf` и QR-код, затем отправляет их в чат.  
Работает **только** с пользователем, чей ID совпадает с `ALLOWED_USER_ID`.

---

## Примечания по безопасности

- Реальный `.env` не должен попадать в репозиторий (он в `.gitignore`).  
- Для примера используется `.env.example` без чувствительных данных.  
- При утечке токенов/паролей необходимо их **ротировать** и перезапустить контейнеры.

---

## Структура проекта

```
.
├── app/                     # wg-transformer (API для трансформации конфигов)
├── bot/                     # Telegram-бот и интеграция с MikroTik
├── docker-compose.yml        # описание сервисов
├── .env.example              # пример переменных окружения
└── README.md                 # документация проекта
```

---

## Быстрый старт

```bash
cp .env.example .env
# Заполнить .env своими данными
docker compose up -d --build
```

После запуска отправьте боту команду `/newpeer` в Telegram.
