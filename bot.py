# bot.py
import aiohttp
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

from config import TELEGRAM_TOKEN
from movie_engine import MovieEngine
from database import MovieDB

# Inicialización
engine = MovieEngine()
db = MovieDB()
estados_usuarios = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicio del bot y reinicio de estados"""
    user = update.effective_user
    await db.registrar_usuario(user.id, user.first_name)
    
    # Reiniciamos el estado del usuario
    estados_usuarios[user.id] = {'paso': 'p1'}

    keyboard = [
        [InlineKeyboardButton("🎬 Películas", callback_data='p1_movie'),
         InlineKeyboardButton("📺 Series", callback_data='p1_tv')],
        [InlineKeyboardButton("🎞️ Documentales", callback_data='p1_doc')]
    ]
    
    texto = f"✨ ¡Hola, *{user.first_name}*! ✨\n¿Qué aventura quieres vivir hoy? 🍿"
    
    # MEJORA: Si viene de un botón (callback), enviamos un mensaje nuevo. 
    # Telegram no permite editar un mensaje con foto para convertirlo en texto.
    if update.callback_query:
        await update.callback_query.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def procesar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    # Answer siempre al inicio
    await query.answer()

    # Lógica de reinicio: borramos el mensaje anterior para limpiar el chat
    if data == 'reset_game':
        try:
            await query.message.delete()
        except:
            pass
        await start(update, context)
        return

    # Verificación de sesión segura
    if user_id not in estados_usuarios:
        estados_usuarios[user_id] = {'paso': 'p1'}
    
    estado = estados_usuarios[user_id]

    # --- NAVEGACIÓN ---
    if data in ['p1_movie', 'p1_tv']:
        estado.update({'tipo': data.split('_')[1], 'es_doc': False})
        keyboard = [[InlineKeyboardButton("🎨 Animado", callback_data='p2_anim'),
                     InlineKeyboardButton("🎭 Personas Reales", callback_data='p2_live')]]
        await query.edit_message_text("¿Animación o actores reales? 🎭", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('p2_'):
        estado['animado'] = (data == 'p2_anim')
        keyboard = [
            [InlineKeyboardButton("💥 Acción", callback_data='p3_28'), InlineKeyboardButton("😂 Comedia", callback_data='p3_35')],
            [InlineKeyboardButton("👻 Terror", callback_data='p3_27'), InlineKeyboardButton("🌌 Sci-Fi", callback_data='p3_878')],
            [InlineKeyboardButton("🕵️ Misterio", callback_data='p3_9648'), InlineKeyboardButton("💖 Romance", callback_data='p3_10749')],
            [InlineKeyboardButton("🧙 Fantasía", callback_data='p3_14'), InlineKeyboardButton("🔪 Crimen", callback_data='p3_80')]
        ]
        await query.edit_message_text("🎭 ¿Qué género prefieres?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'p1_doc':
        estado.update({'tipo': 'movie', 'es_doc': True})
        keyboard = [
            [InlineKeyboardButton("🌿 Naturaleza", callback_data='p4_99'), InlineKeyboardButton("📜 Historia", callback_data='p4_36')],
            [InlineKeyboardButton("⚖️ Crimen Real", callback_data='p4_80'), InlineKeyboardButton("🚀 Ciencia", callback_data='p4_10770')],
            [InlineKeyboardButton("⚽ Deportes", callback_data='p4_10752'), InlineKeyboardButton("🎶 Música", callback_data='p4_10402')]
        ]
        await query.edit_message_text("🌍 ¿Qué temática quieres descubrir?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('p3_') or data.startswith('p4_'):
        estado['genero_id'] = int(data.split('_')[1])
        await query.edit_message_text("🔮 *Consultando múltiples fuentes en paralelo...*", parse_mode='Markdown')
        await context.bot.send_chat_action(chat_id=user_id, action=constants.ChatAction.TYPING)
        await enviar_resultado(query, user_id, estado)

async def enviar_resultado(query, user_id, estado):
    async with aiohttp.ClientSession() as session:
        res = await engine.descubrir_contenido(
            session, 
            estado['tipo'], 
            estado['genero_id'], 
            estado.get('animado', False), 
            estado.get('es_doc')
        )
        
        if not res:
            btn_error = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Reintentar", callback_data='reset_game')]])
            await query.message.reply_text("😔 No encontré resultados. ¡Prueba otra categoría!", reply_markup=btn_error)
            return

        item = random.choice(res[:12])
        titulo = item.get('title') or item.get('name') or "Desconocido"
        
        # Concurrencia para OMDb
        tarea_ratings = engine.obtener_ratings_omdb(session, titulo)
        
        # Link de YouTube
        busqueda_yt = f"{titulo} trailer oficial español".replace(" ", "+")
        url_youtube = f"https://www.youtube.com/results?search_query={busqueda_yt}"
        
        texto_ratings = await tarea_ratings
        
        puntos_tmdb = item.get('vote_average', 0)
        anio = (item.get('release_date') or item.get('first_air_date') or "----")[:4]
        desc = item.get('overview', 'Sin descripción disponible.')
        poster_path = item.get('poster_path')
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

        keyboard = [
            [InlineKeyboardButton("📺 Ver Tráiler (YouTube)", url=url_youtube)],
            [InlineKeyboardButton("🔄 Nueva Búsqueda", callback_data='reset_game')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        texto_final = (
            f"🎯 *¡Bingo!*\n\n"
            f"🎬 *{titulo.upper()}* ({anio})\n"
            f"{texto_ratings}\n"
            f"📊 Popularidad TMDB: `{puntos_tmdb}/10` 🍿\n\n"
            f"📝 _{desc[:400]}..._"
        )
        
        try:
            if poster_url:
                await query.message.reply_photo(photo=poster_url, caption=texto_final, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await query.message.reply_text(texto_final, parse_mode='Markdown', reply_markup=reply_markup)
        except:
            await query.message.reply_text(texto_final, parse_mode='Markdown', reply_markup=reply_markup)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(procesar_callback))
    
    print("---------------------------------------")
    print("🚀 Bot Maestro de Cine Activo")
    print("---------------------------------------")
    app.run_polling(drop_pending_updates=True)