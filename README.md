# Mikrotik WG Bot

Два сервиса:
- wg-transformer — API для преобразования WireGuard-конфигов
- wg-telegram-bot — Telegram-бот: создаёт peer на MikroTik, генерирует .conf и QR

Запуск:
docker compose up -d --build

Файл .env не должен попасть в репозиторий.
