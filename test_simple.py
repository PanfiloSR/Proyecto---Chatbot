# test_simple.py - Versión ultra simple sin logging excesivo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_TOKEN

# Logging mínimo
import logging
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("✅ /start recibido!")
    keyboard = [
        [InlineKeyboardButton("Test 1", callback_data="1")],
        [InlineKeyboardButton("Test 2", callback_data="2")],
    ]
    await update.message.reply_text(
        "Presiona un botón:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    print(f"🎯 BOTÓN PRESIONADO: {query.data}")
    await query.edit_message_text(f"Presionaste: {query.data}")

# Crear y ejecutar
app = Application.builder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

print("🚀 Bot iniciado - Envía /start")
app.run_polling(drop_pending_updates=True)