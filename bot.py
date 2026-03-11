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

# Diccionario para guardar el estado del juego de cada usuario
# Estructura: { user_id: { 'nombre': str, 'tipo': str, 'sangre': bool, 'animada': bool, 'paso': int } }
estados_usuarios = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 ¡Bienvenido al Akinator de Cine! Dime el nombre de algo que te guste y trataré de encontrar recomendaciones perfectas basadas en tus gustos.")

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    query = update.message.text
    
    # Iniciamos el estado para este usuario
    estados_usuarios[user_id] = {'nombre': query, 'paso': 1}

    keyboard = [
        [InlineKeyboardButton("🎬 Película", callback_data='tipo_movie'),
         InlineKeyboardButton("📺 Serie", callback_data='tipo_tv')]
    ]
    await update.message.reply_text(f"¿'{query}' es película o serie?", reply_markup=InlineKeyboardMarkup(keyboard))

async def procesar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_click = update.callback_query
    user_id = query_click.from_user.id
    data = query_click.data
    
    await query_click.answer()

    if user_id not in estados_usuarios:
        await query_click.edit_message_text("❌ Sesión expirada. Escribe el nombre de nuevo.")
        return

    estado = estados_usuarios[user_id]

    # PASO 1: Selección de Tipo
    if data.startswith('tipo_'):
        estado['tipo'] = data.replace('tipo_', '')
        estado['paso'] = 2
        keyboard = [
            [InlineKeyboardButton("Sí, mucha 🩸", callback_data='sangre_true'),
             InlineKeyboardButton("No, tranqui 😇", callback_data='sangre_false')]
        ]
        await query_click.edit_message_text("¿Te gusta que tenga mucha sangre/acción fuerte?", reply_markup=InlineKeyboardMarkup(keyboard))

    # PASO 2: Selección de Sangre
    elif data.startswith('sangre_'):
        estado['sangre'] = data == 'sangre_true'
        estado['paso'] = 3
        keyboard = [
            [InlineKeyboardButton("Sí 🎨", callback_data='anim_true'),
             InlineKeyboardButton("No (Live Action) 🎭", callback_data='anim_false')]
        ]
        await query_click.edit_message_text("¿Prefieres que sea animada?", reply_markup=InlineKeyboardMarkup(keyboard))

    # PASO 3: Resultado final (Adivinar/Recomendar)
    elif data.startswith('anim_'):
        estado['animada'] = data == 'anim_true'
        await query_click.edit_message_text("🧠 Analizando tus gustos... filtrando catálogo...")
        
        # Lógica de filtrado
        await realizar_busqueda_final(query_click, user_id, estado)

async def realizar_busqueda_final(query_click, user_id, estado):
    async with aiohttp.ClientSession() as session:
        # Buscamos la obra base
        base = await engine.buscar_item(session, estado['nombre'], estado['tipo'])
        
        if not base:
            await query_click.edit_message_text("No encontré la obra original, pero intentaré adivinar algo para ti.")
            return

        # Obtenemos muchas recomendaciones para filtrar
        todas_recs = await engine.obtener_muchas_recs(session, base['id'], estado['tipo'])
        
        # FILTRADO TIPO AKINATOR
        filtradas = []
        for r in todas_recs:
            es_animada = 16 in r.get('genre_ids', []) # 16 es el ID de animación en TMDB
            es_sangrienta = any(g in [28, 80, 27] for g in r.get('genre_ids', [])) # Acción, Crimen, Terror

            # Aplicamos los filtros del usuario
            if es_animada == estado['animada']:
                if estado['sangre'] == es_sangrienta:
                    filtradas.append(r)

        if filtradas:
            # Elegimos una al azar de las que pasaron el filtro para que parezca que "adivina"
            elegida = random.choice(filtradas)
            nombre = elegida.get('title') or elegida.get('name')
            desc = elegida.get('overview', 'Sin descripción.')
            
            mensaje = f"🔮 ¡Adiviné! Basado en tus filtros, te encantará:\n\n"
            mensaje += f"⭐ *{nombre}*\n📝 _{desc[:250]}..._"
            
            await query_click.message.reply_text(mensaje, parse_mode='Markdown')
        else:
            await query_click.message.reply_text("😔 Mis poderes fallaron. No encontré nada exacto con esos filtros.")
        
        # Limpiamos el estado para la siguiente búsqueda
        del estados_usuarios[user_id]

if __name__ == '__main__':
    # Aumentamos los tiempos a 100 segundos para redes escolares/lentas
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(100).connect_timeout(100).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), manejar_mensaje))
    app.add_handler(CallbackQueryHandler(procesar_callback))

    print("------------------------------------------")
    print("🚀 Akinator de Cine iniciado")
    print("💡 Si hay lag, el bot esperará hasta 100s")
    print("------------------------------------------")
    
    # Agregamos parámetros de pool_timeout para mayor estabilidad
    app.run_polling(poll_interval=1.0, timeout=30)