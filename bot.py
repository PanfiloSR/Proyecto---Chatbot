# bot.py
import logging
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters,
)

from config import TELEGRAM_TOKEN
from movie_engine import MovieEngine, crear_sesion, GENEROS_MOVIE, TEMATICAS_DOC

# Al inicio del archivo bot.py, cambia:
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.DEBUG,  # Cambiado de INFO a DEBUG
)
log = logging.getLogger(__name__)

engine  = MovieEngine()
estados = {}   # { user_id: dict }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de teclado
# ─────────────────────────────────────────────────────────────────────────────
def _kb(filas: list) -> InlineKeyboardMarkup:
    resultado = []
    for fila in filas:
        if not fila:
            continue
        if isinstance(fila[0], tuple):
            resultado.append([InlineKeyboardButton(t, callback_data=d) for t, d in fila])
        else:
            resultado.append(fila)   # ya son InlineKeyboardButton
    return InlineKeyboardMarkup(resultado)

BTN_INICIO = [("🏠 Menú principal", "inicio")]

def _teclado_generos(prefijo: str, fuente: dict,
                     excluir: set | None = None) -> InlineKeyboardMarkup:
    excluir = excluir or set()
    items   = [(nombre, f"{prefijo}_{gid}")
               for gid, nombre in fuente.items() if gid not in excluir]
    filas   = [items[i:i+2] for i in range(0, len(items), 2)]
    filas.append(BTN_INICIO)
    return _kb(filas)


# ─────────────────────────────────────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    estados[user.id] = {"paso": "menu"}

    texto = (
        f"✨ ¡Hola, *{user.first_name}*! Soy tu guía de cine y series 🎬\n\n"
        "¿Qué quieres hacer hoy?"
    )
    teclado = _kb([
        [("🔭 Descubrir algo nuevo",     "inicio_descubrir")],
        [("🎯 Buscar contenido similar", "inicio_similar")],
        [("🎭 Buscar por Actor",         "inicio_talento")],
    ])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            texto, reply_markup=teclado, parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            texto, reply_markup=teclado, parse_mode="Markdown"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Callback handler ÚNICO
# ─────────────────────────────────────────────────────────────────────────────
async def procesar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q       = update.callback_query
    user_id = q.from_user.id
    data    = q.data
    await q.answer()

    if user_id not in estados:
        estados[user_id] = {"paso": "menu"}
    estado = estados[user_id]
    log.info("CB user=%s data=%s", user_id, data)

    # ── Menú ──────────────────────────────────────────────────────────────────
    if data == "inicio":
        await start(update, context)
        return

    # ══════════════════════════════════════════════════════════════════════════
    # RAMA 1 — DESCUBRIMIENTO
    # ══════════════════════════════════════════════════════════════════════════
    if data == "inicio_descubrir":
        estado.update({"rama": "descubrir"})
        await q.edit_message_text(
            "¿Qué tipo de contenido buscas?",
            reply_markup=_kb([
                [("🎬 Película",   "desc_formato_movie"),
                 ("📺 Serie",      "desc_formato_tv")],
                [("🎞️ Documental", "desc_formato_doc")],
                BTN_INICIO,
            ])
        )
        return

    elif data in ("desc_formato_movie", "desc_formato_tv"):
        tipo = "movie" if data == "desc_formato_movie" else "tv"
        estado.update({"tipo": tipo, "es_doc": False})
        await q.edit_message_text(
            "¿Prefieres animación o actores reales?",
            reply_markup=_kb([
                [("🎨 Animación",      "desc_visual_anim"),
                 ("🎭 Actores reales", "desc_visual_live")],
                BTN_INICIO,
            ])
        )
        return

    elif data == "desc_formato_doc":
        estado.update({"tipo": "movie", "es_doc": True, "es_animado": False})
        items = [(nombre, f"desc_genero_{gid}") for gid, nombre in TEMATICAS_DOC.items()]
        filas = [items[i:i+2] for i in range(0, len(items), 2)]
        filas.append(BTN_INICIO)
        await q.edit_message_text("🎞️ ¿Qué temática te interesa?",
                                   reply_markup=_kb(filas))
        return

    elif data in ("desc_visual_anim", "desc_visual_live"):
        estado["es_animado"] = (data == "desc_visual_anim")
        await q.edit_message_text(
            "🎭 ¿Qué género prefieres?",
            reply_markup=_teclado_generos("desc_genero", GENEROS_MOVIE, excluir={16, 99})
        )
        return

    elif data.startswith("desc_genero_"):
        genero_id = int(data.split("_")[2])
        estado["genero_id"] = genero_id
        await q.edit_message_text("🔮 *Buscando la mejor opción...*",
                                   parse_mode="Markdown")
        await context.bot.send_chat_action(chat_id=user_id,
                                           action=constants.ChatAction.TYPING)
        async with crear_sesion() as session:
            res = await engine.descubrir(
                session,
                estado.get("tipo", "movie"),
                genero_id,
                estado.get("es_animado", False),
                estado.get("es_doc", False),
            )
        if not res:
            await q.message.reply_text(
                "😔 Sin resultados. Prueba otra combinación.",
                reply_markup=_kb([BTN_INICIO])
            )
            return
        await _enviar_tarjeta(q, random.choice(res[:12]),
                              estado.get("tipo", "movie"))
        return

    # ══════════════════════════════════════════════════════════════════════════
    # RAMA 2 — SIMILITUD (NUEVA VERSIÓN CON SELECCIÓN)
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "inicio_similar":
        estado.update({"rama": "similar", "paso": "esperando_titulo"})
        await q.edit_message_text(
            "🎬 *¿Qué has visto recientemente?*\n\n"
            "Escribe el nombre de la película o serie que te gustó "
            "y buscaré contenido similar por palabras clave 🏷️",
            parse_mode="Markdown"
        )
        return

    elif data == "similar_ir_descubrir":
        estado.update({"rama": "descubrir"})
        await q.edit_message_text(
            "Sin problema, usemos el modo exploración 🔭\n\n¿Qué tipo de contenido buscas?",
            reply_markup=_kb([
                [("🎬 Película",   "desc_formato_movie"),
                 ("📺 Serie",      "desc_formato_tv")],
                [("🎞️ Documental", "desc_formato_doc")],
                BTN_INICIO,
            ])
        )
        return

    # Nueva sección: Selección de título de la lista de candidatos
    elif data.startswith("similar_sel_"):
        parts = data.split("_")
        tmdb_id = int(parts[2])
        tipo = parts[3]  # movie o tv
        
        await q.edit_message_text(
            f"🎬 *Procesando selección...*\n\nBuscando recomendaciones basadas en tu elección.",
            parse_mode="Markdown"
        )
        
        await context.bot.send_chat_action(chat_id=user_id,
                                           action=constants.ChatAction.TYPING)
        
        async with crear_sesion() as session:
            resultado = await engine.recomendar_por_id(session, tmdb_id, tipo)
        
        if not resultado:
            await q.message.reply_text(
                "😔 No pude encontrar recomendaciones para esta película/serie.",
                reply_markup=_kb([BTN_INICIO])
            )
            return
        
        semilla = resultado["semilla"]
        recs = resultado["recomendaciones"]
        
        # Enviar confirmación
        await q.message.reply_text(
            f"✅ Basándome en *{semilla['titulo']}* ({semilla['anio']})\n"
            f"aquí tienes 3 recomendaciones por palabras clave 🏷️:",
            parse_mode="Markdown"
        )
        
        # Enviar recomendaciones
        for item in recs:
            async with crear_sesion() as session:
                tarjeta = await engine.construir_tarjeta(session, item, tipo)
            teclado = _kb([
                [InlineKeyboardButton("📺 Ver tráiler", url=tarjeta["url_yt"])],
                [("🔄 Nueva búsqueda", "inicio")],
            ])
            try:
                if tarjeta["poster_url"]:
                    await q.message.reply_photo(
                        photo=tarjeta["poster_url"],
                        caption=tarjeta["texto"],
                        parse_mode="Markdown",
                        reply_markup=teclado,
                    )
                else:
                    await q.message.reply_text(
                        tarjeta["texto"], parse_mode="Markdown",
                        reply_markup=teclado
                    )
            except Exception as e:
                log.warning("reply_photo falló (%s), usando texto", e)
                await q.message.reply_text(
                    tarjeta["texto"], parse_mode="Markdown",
                    reply_markup=teclado
                )
        return

    # ══════════════════════════════════════════════════════════════════════════
    # RAMA 3 — TALENTO
    # ══════════════════════════════════════════════════════════════════════════
    elif data == "inicio_talento":
        estado.update({"rama": "talento", "paso": "esperando_actor"})
        await q.edit_message_text(
            "🎭 *¿Qué actor o actriz quieres ver?*\n\n"
            "Escribe su nombre 👇",
            parse_mode="Markdown"
        )
        return

    elif data.startswith("talento_persona_"):
        person_id   = int(data.split("_")[2])
        person_name = estado.get("actor_nombre", "el actor/actriz")
        estado["person_id"] = person_id
        await q.edit_message_text(
            f"✅ *{person_name}* identificado/a.\n\n¿En qué género quieres verlo/la?",
            parse_mode="Markdown",
            reply_markup=_teclado_generos("talento_genero", GENEROS_MOVIE,
                                          excluir={16, 99})
        )
        return

    elif data.startswith("talento_genero_"):
        genero_id = int(data.split("_")[2])
        person_id = estado.get("person_id")
        if not person_id:
            await q.edit_message_text("⚠️ Sesión perdida.",
                                       reply_markup=_kb([BTN_INICIO]))
            return
        await q.edit_message_text("🎬 *Buscando películas...*",
                                   parse_mode="Markdown")
        await context.bot.send_chat_action(chat_id=user_id,
                                           action=constants.ChatAction.TYPING)
        async with crear_sesion() as session:
            res = await engine.descubrir_por_actor_y_genero(
                session, person_id, genero_id
            )
        if not res:
            await q.message.reply_text(
                "😔 Sin resultados para ese actor en ese género.",
                reply_markup=_kb([
                    [(f"🔄 Cambiar género", f"talento_persona_{person_id}")],
                    BTN_INICIO,
                ])
            )
            return
        await _enviar_tarjeta(q, res[0], "movie")
        return


# ─────────────────────────────────────────────────────────────────────────────
# Handler de texto libre
# ─────────────────────────────────────────────────────────────────────────────
async def procesar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto   = update.message.text.strip()

    if user_id not in estados:
        estados[user_id] = {}
    estado = estados[user_id]
    rama   = estado.get("rama")
    paso   = estado.get("paso")
    log.info("TXT user=%s rama=%s paso=%s texto='%s'", user_id, rama, paso, texto)

    # ══════════════════════════════════════════════════════════════════════════
    # RAMA 2 — captura de título (NUEVA VERSIÓN)
    # ══════════════════════════════════════════════════════════════════════════
    if rama == "similar" and paso == "esperando_titulo":
        estado["paso"] = "buscando"
        
        msg = await update.message.reply_text(
            f"🔎 Buscando *{texto}*...",
            parse_mode="Markdown"
        )
        await context.bot.send_chat_action(chat_id=user_id,
                                           action=constants.ChatAction.TYPING)
        
        async with crear_sesion() as session:
            candidatos = await engine.buscar_titulos(session, texto)
        
        try:
            await msg.delete()
        except Exception:
            pass
        
        if not candidatos:
            estado["paso"] = "esperando_titulo"
            await update.message.reply_text(
                f"😔 No encontré *{texto}* en TMDB.\n\n¿Qué quieres hacer?",
                parse_mode="Markdown",
                reply_markup=_kb([
                    [("🔭 Ir a Descubrimiento", "similar_ir_descubrir")],
                    [("✏️ Escribir otro título", "inicio_similar")],
                    BTN_INICIO,
                ])
            )
            return
        
        # Guardar candidatos en el estado (opcional, para referencia)
        estado["candidatos"] = candidatos
        estado["paso"] = "seleccionando_titulo"
        
        # Crear botones para cada candidato
        filas = []
        for i, cand in enumerate(candidatos[:8]):  # Máximo 8 para no saturar
            callback_data = f"similar_sel_{cand['id']}_{cand['media_type']}"
            filas.append([(cand["display_text"], callback_data)])
        
        # Añadir botones de navegación
        filas.append([("✏️ Buscar otro título", "inicio_similar")])
        filas.append(BTN_INICIO)
        
        await update.message.reply_text(
            f"🔍 Encontré {len(candidatos)} coincidencias. ¿A cuál te refieres?",
            reply_markup=_kb(filas),
            parse_mode="Markdown"
        )
        return

    # ══════════════════════════════════════════════════════════════════════════
    # RAMA 3 — captura de nombre del actor
    # ══════════════════════════════════════════════════════════════════════════
    elif rama == "talento" and paso == "esperando_actor":
        estado.update({"paso": "buscando", "actor_nombre": texto})

        msg = await update.message.reply_text(
            f"🔎 Buscando a *{texto}*...", parse_mode="Markdown"
        )
        await context.bot.send_chat_action(chat_id=user_id,
                                           action=constants.ChatAction.TYPING)

        async with crear_sesion() as session:
            personas = await engine.buscar_persona(session, texto)

        log.info("buscar_persona('%s') → %d", texto, len(personas))

        try:
            await msg.delete()
        except Exception:
            pass

        if not personas:
            estado["paso"] = "esperando_actor"   # reset
            await update.message.reply_text(
                f"😔 No encontré a *{texto}* en TMDB.\n"
                "Prueba con el nombre en inglés o verifica la ortografía.",
                parse_mode="Markdown",
                reply_markup=_kb([
                    [("✏️ Intentar con otro nombre", "inicio_talento")],
                    BTN_INICIO,
                ])
            )
            return

        filas = []
        for p in personas:
            nombre = p.get("name", "Desconocido")
            rol    = p.get("known_for_department", "")
            obras  = ", ".join(
                k.get("title") or k.get("name") or ""
                for k in p.get("known_for", [])[:2]
                if k.get("title") or k.get("name")
            )
            linea = f"🎭 {nombre}"
            if rol:   linea += f" — {rol}"
            if obras: linea += f" ({obras})"
            filas.append([(linea, f"talento_persona_{p['id']}")])

        filas.append([("✏️ Ninguno → buscar otro nombre", "inicio_talento")])
        filas.append(BTN_INICIO)

        await update.message.reply_text(
            f"¿A cuál *{texto}* te refieres?",
            reply_markup=_kb(filas),
            parse_mode="Markdown"
        )
        return

    else:
        await update.message.reply_text(
            "Usa el menú para navegar 👇",
            reply_markup=_kb([BTN_INICIO])
        )
        return


# ─────────────────────────────────────────────────────────────────────────────
# Enviar tarjeta (flujos de descubrimiento y talento)
# ─────────────────────────────────────────────────────────────────────────────
async def _enviar_tarjeta(q, item: dict, tipo: str):
    async with crear_sesion() as session:
        tarjeta = await engine.construir_tarjeta(session, item, tipo)

    teclado = _kb([
        [InlineKeyboardButton("📺 Ver tráiler en YouTube", url=tarjeta["url_yt"])],
        [("🔄 Nueva búsqueda", "inicio")],
    ])
    texto = tarjeta["texto"]

    try:
        if tarjeta["poster_url"]:
            await q.message.reply_photo(
                photo=tarjeta["poster_url"],
                caption=texto,
                parse_mode="Markdown",
                reply_markup=teclado,
            )
        else:
            await q.message.reply_text(texto, parse_mode="Markdown",
                                        reply_markup=teclado)
    except Exception as e:
        log.warning("reply_photo falló (%s), fallback texto", e)
        await q.message.reply_text(texto, parse_mode="Markdown",
                                    reply_markup=teclado)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(procesar_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_texto))

    log.info("Bot iniciado — Ramas: Descubrimiento · Similitud · Talento")
    app.run_polling(drop_pending_updates=True)