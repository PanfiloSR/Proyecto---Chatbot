# bot.py
import aiohttp
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from config import TELEGRAM_TOKEN
from movie_engine import MovieEngine
from database import MovieDB

engine = MovieEngine()
db = MovieDB()

estados_usuarios = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    await db.registrar_usuario(user_id, user_name)
    
    estados_usuarios[user_id] = {'paso': 'pregunta_1'}

    keyboard = [
        [InlineKeyboardButton("🎬 Películas", callback_data='p1_movie'),
         InlineKeyboardButton("📺 Series", callback_data='p1_tv')],
        [InlineKeyboardButton("🎞️ Documentales", callback_data='p1_doc')]
    ]
    
    texto = f"¡Hola {user_name}! 🤖 ¿Qué tipo de contenido te apetece hoy?"
    
    if update.message:
        await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard))

async def procesar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_click = update.callback_query
    user_id = query_click.from_user.id
    data = query_click.data
    await query_click.answer()

    if data == 'reset_game':
        await start(update, context)
        return

    estado = estados_usuarios.get(user_id)
    if not estado: return

    # --- CAMINO: PELÍCULA O SERIE ---
    if data in ['p1_movie', 'p1_tv']:
        estado['tipo'] = data.split('_')[1]
        estado['paso'] = 'pregunta_2'
        keyboard = [
            [InlineKeyboardButton("🎨 Animado", callback_data='p2_anim'),
             InlineKeyboardButton("🎭 Live Action", callback_data='p2_live')]
        ]
        await query_click.edit_message_text("¿Prefieres algo Animado o Live Action?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('p2_'):
        estado['animado'] = (data == 'p2_anim')
        estado['paso'] = 'pregunta_3'
        
        # CATEGORÍAS EXTENDIDAS PARA PELIS/SERIES
        keyboard = [
            [InlineKeyboardButton("💥 Acción", callback_data='p3_28'),
             InlineKeyboardButton("😂 Comedia", callback_data='p3_35')],
            [InlineKeyboardButton("👻 Terror", callback_data='p3_27'),
             InlineKeyboardButton("🌌 Sci-Fi", callback_data='p3_878')],
            [InlineKeyboardButton("🕵️ Misterio", callback_data='p3_9648'),
             InlineKeyboardButton("💖 Romance", callback_data='p3_10749')],
            [InlineKeyboardButton("🧙 Fantasía", callback_data='p3_14'),
             InlineKeyboardButton("🎸 Musical", callback_data='p3_10402')]
        ]
        await query_click.edit_message_text("Selecciona un género que te guste:", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- CAMINO: DOCUMENTAL ---
    elif data == 'p1_doc':
        estado['tipo'] = 'movie'
        estado['es_doc'] = True
        estado['paso'] = 'pregunta_4'
        
        # CATEGORÍAS EXTENDIDAS PARA DOCUMENTALES
        keyboard = [
            [InlineKeyboardButton("🌿 Naturaleza", callback_data='p4_99'),
             InlineKeyboardButton("📜 Historia", callback_data='p4_36')],
            [InlineKeyboardButton("⚖️ Crimen Real", callback_data='p4_80'),
             InlineKeyboardButton("🚀 Ciencia", callback_data='p4_10770')],
            [InlineKeyboardButton("⚽ Deportes", callback_data='p4_10752'), # Usando guerra/deportes como proxys
             InlineKeyboardButton("🎶 Música", callback_data='p4_10402')]
        ]
        await query_click.edit_message_text("¿Sobre qué quieres aprender hoy?", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- RESULTADO FINAL ---
    elif data.startswith('p3_') or data.startswith('p4_'):
        estado['genero_id'] = int(data.split('_')[1])
        await query_click.edit_message_text("🧠 Filtrando lo mejor de mi base de datos...")
        await generar_recomendacion_final(query_click, user_id, estado)

async def generar_recomendacion_final(query_click, user_id, estado):
    async with aiohttp.ClientSession() as session:
        resultados = await engine.descubrir_contenido(
            session, 
            tipo=estado['tipo'], 
            genero_id=estado['genero_id'],
            es_animado=estado.get('animado', False),
            es_doc=estado.get('es_doc', False)
        )
        
        boton_reset = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Nueva Consulta", callback_data='reset_game')]])

        if resultados:
            elegida = random.choice(resultados[:15])
            titulo = elegida.get('title') or elegida.get('name')
            puntos = elegida.get('vote_average', 0)
            anio = (elegida.get('release_date') or elegida.get('first_air_date') or "----")[:4]
            desc = elegida.get('overview', 'Sin descripción.')
            if len(desc) > 300: desc = desc[:300] + "..."
            
            mensaje = f"🔮 *¡Recomendación encontrada!*\n\n"
            mensaje += f"🎬 *{titulo}* ({anio})\n"
            mensaje += f"⭐ Puntuación: {puntos}/10\n\n"
            mensaje += f"📝 _{desc}_"
            
            await query_click.message.reply_text(mensaje, parse_mode='Markdown', reply_markup=boton_reset)
        else:
            await query_click.message.reply_text("😔 No encontré nada con esos filtros exactos.", reply_markup=boton_reset)
        
        del estados_usuarios[user_id]

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(100).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(procesar_callback))
    app.run_polling()