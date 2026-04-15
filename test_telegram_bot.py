# test_telegram_bot.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_TOKEN

# Configurar logging para ver todo
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start"""
    print("\n🔥 /start recibido!")
    
    keyboard = [
        [InlineKeyboardButton("Test Button 1", callback_data="test1")],
        [InlineKeyboardButton("Test Button 2", callback_data="test2")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 Bot de prueba - Haz clic en un botón:",
        reply_markup=reply_markup
    )
    print("✅ Mensaje de inicio enviado con botones")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones"""
    query = update.callback_query
    user = query.from_user
    
    print(f"\n🔔 CALLBACK RECIBIDO!")
    print(f"   Usuario: {user.first_name} (id={user.id})")
    print(f"   Data: {query.data}")
    
    # Responder al callback
    await query.answer()
    
    # Editar el mensaje
    await query.edit_message_text(
        f"✅ ¡Funciona! Recibiste: {query.data}\n\n"
        f"Usuario: {user.first_name}\n"
        f"ID: {user.id}"
    )
    print("✅ Mensaje actualizado")

def main():
    """Inicia el bot"""
    print("\n" + "="*50)
    print("INICIANDO BOT DE PRUEBA")
    print("="*50)
    
    # Crear la aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Registrar handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Handlers registrados")
    print("✅ Bot iniciado - Esperando mensajes...")
    print("👉 Envía /start a tu bot en Telegram\n")
    
    # Iniciar el bot
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()