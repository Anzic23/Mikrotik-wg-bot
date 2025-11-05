import os
import io
import logging
import qrcode
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from mikrotik import MikrotikAPI

# ===== Настройки доступа =====
ALLOWED_USER_ID = 235378143  # только этот Telegram ID имеет доступ

# ===== Состояния диалога =====
WAITING_FOR_NAME = 1
WAITING_FOR_ALLOWED_IPS = 2

# Кнопки AllowedIPs
CHOICES = [["Базовый (YouTube, Instagram, FB)"], ["Весь трафик"]]

# Логирование
logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("wg-bot")

mt = MikrotikAPI()

# ===== Ограничение доступа =====
async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id if update and update.effective_user else None
    if user_id != ALLOWED_USER_ID:
        try:
            if update.message:
                await update.message.reply_text("⛔️ У вас нет доступа к этому боту.")
        except Exception:
            pass
        log.warning("Denied access from user_id=%s", user_id)
        return False
    return True

# ===== Хэндлеры =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return
    await update.message.reply_text(
        "Привет 👋\n"
        "Команда: /newpeer — создам WG клиента, пришлю .conf и QR 📲"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text("❌ Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def newpeer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return ConversationHandler.END
    await update.message.reply_text("Введите имя нового пира:")
    return WAITING_FOR_NAME

async def newpeer_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return ConversationHandler.END
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("Имя пустое, введите ещё раз:")
        return WAITING_FOR_NAME

    context.user_data["peer_name"] = name
    reply_markup = ReplyKeyboardMarkup(CHOICES, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"Имя пира: *{name}*\nТеперь выберите тип AllowedIPs 👇",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return WAITING_FOR_ALLOWED_IPS

async def newpeer_allowed_ips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return ConversationHandler.END
    choice = (update.message.text or "").strip()
    peer_name = context.user_data.get("peer_name", "Client")
    log.info("Create peer: name=%s, choice=%s", peer_name, choice)

    # AllowedIPs профиль
    if "Весь трафик" in choice:
        allowed_ips = "0.0.0.0/0, ::/0"
        suffix = "_all"
    else:
        # Базовый профиль (сокращён). Если хочешь — вставь сюда твой полный список.
        allowed_ips = (
            "192.168.220.1/32, 10.200.0.0/14, 31.13.24.0/21, 31.13.64.0/18, "
            "45.64.40.0/22, 57.141.0.0/24, 57.141.2.0/24, 57.141.4.0/24, "
            "57.141.6.0/24, 57.141.8.0/24, 57.141.10.0/24, 57.141.12.0/24, "
            "57.144.0.0/14, 66.220.144.0/20, 69.63.176.0/20, 69.171.224.0/19"
        )
        suffix = "_base"

    await update.message.reply_text(
        f"Создаю peer *{peer_name}* ({choice})…",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

    try:
        # Создаём peer на MikroTik и получаем конфиг
        config = mt.add_peer(peer_name)

        # Подменяем AllowedIPs в конфиге
        lines = config.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("AllowedIPs"):
                lines[i] = f"AllowedIPs = {allowed_ips}"
        config = "\n".join(lines)

        # Имя файла
        filename = f"wg-{peer_name}{suffix}.conf".replace(" ", "_")

        # Файл
        await update.message.reply_document(document=io.BytesIO(config.encode()), filename=filename)

        # QR
        img = qrcode.make(config)
        bio = io.BytesIO()
        bio.name = f"{filename}.png"
        img.save(bio, "PNG")
        bio.seek(0)
        await update.message.reply_photo(photo=bio, caption="QR-код для подключения 📲")

    except Exception as e:
        log.exception("newpeer error")
        await update.message.reply_text(f"❌ Ошибка при создании peer: {e}")

    context.user_data.clear()
    return ConversationHandler.END

# ===== Обработчик ошибок чтобы не падать молча =====
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error: %s", context.error)
    try:
        if isinstance(update, Update) and update.effective_user and update.effective_message:
            if await check_access(update, context):
                await update.effective_message.reply_text("⚠️ Внутренняя ошибка. Проверь логи контейнера.")
    except Exception:
        pass

# ===== Очистка вебхука =====
async def on_startup(app):
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        log.info("Webhook deleted (if any).")
    except Exception:
        log.warning("Cannot delete webhook (maybe none).")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    app = ApplicationBuilder().token(token).build()
    app.post_init = on_startup

    conv = ConversationHandler(
        entry_points=[CommandHandler("newpeer", newpeer_start)],
        states={
            WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, newpeer_name)],
            WAITING_FOR_ALLOWED_IPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, newpeer_allowed_ips)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_error_handler(on_error)

    log.info("Bot starting…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    log.info("Bot stopped.")

if __name__ == "__main__":
    main()
