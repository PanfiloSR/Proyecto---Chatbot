# movie_engine.py
import aiohttp
import logging
import json
from config import TMDB_API_KEY, OMDB_API_KEY

log = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
OMDB_BASE = "http://www.omdbapi.com/"
IMG_BASE  = "https://image.tmdb.org/t/p/w500"

# ─────────────────────────────────────────────────────────────────────────────
# Géneros oficiales TMDB
# ─────────────────────────────────────────────────────────────────────────────
GENEROS_MOVIE = {
    28:    "💥 Acción",
    12:    "🌿 Aventura",
    35:    "😂 Comedia",
    80:    "🔪 Crimen",
    18:    "🎭 Drama",
    10751: "👨‍👩‍👧 Familia",
    14:    "🧙 Fantasía",
    36:    "🏛️ Historia",
    27:    "👻 Terror",
    10402: "🎵 Música",
    9648:  "🕵️ Misterio",
    10749: "💖 Romance",
    878:   "🌌 Ciencia Ficción",
    53:    "🔦 Thriller",
    10752: "⚔️ Bélica",
    37:    "🤠 Western",
}

GENEROS_TV = {
    10759: "💥 Acción & Aventura",
    16:    "🎨 Animación",
    35:    "😂 Comedia",
    80:    "🔪 Crimen",
    18:    "🎭 Drama",
    10751: "👨‍👩‍👧 Familia",
    9648:  "🕵️ Misterio",
    10765: "🌌 Sci-Fi & Fantasía",
    10768: "⚔️ Bélica & Política",
    37:    "🤠 Western",
}

TEMATICAS_DOC = {
    36:    "🏛️ Historia",
    80:    "🩸 Crimen Real",
    878:   "🔬 Ciencia & Tecnología",
    10402: "🎶 Música",
    53:    "🕵️ Misterio & Conspiración",
    10752: "⚔️ Guerra & Conflictos",
    10751: "👨‍👩‍👧 Familia & Sociedad",
}


# ─────────────────────────────────────────────────────────────────────────────
# Sesión HTTP
# ─────────────────────────────────────────────────────────────────────────────
def crear_sesion() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=20),
        headers={"Accept": "application/json", "User-Agent": "CineBot/2.0"},
    )


class MovieEngine:

    def __init__(self):
        if not TMDB_API_KEY:
            raise ValueError("TMDB_API_KEY no está configurada en config.py")
        self.key  = TMDB_API_KEY
        self.omdb = OMDB_API_KEY
        log.info("MovieEngine listo. Key: ...%s", self.key[-4:])

    # ── GET helper ────────────────────────────────────────────────────────────
    async def _get(self, session: aiohttp.ClientSession,
                   url: str, params: dict) -> dict:
        try:
            async with session.get(url, params=params) as r:
                body = await r.text()
                log.debug("GET %s → %s (%d bytes)", url, r.status, len(body))
                if r.status == 200:
                    return json.loads(body)
                log.warning("TMDB %s → status %s: %s", url, r.status, body[:200])
        except aiohttp.ServerTimeoutError:
            log.error("Timeout: %s", url)
        except aiohttp.ClientConnectorError as e:
            log.error("Sin conexión: %s — %s", url, e)
        except Exception as e:
            log.error("Error GET %s: %s", url, e, exc_info=True)
        return {}

    def _p(self, extra: dict | None = None) -> dict:
        base = {"api_key": self.key, "language": "es-ES"}
        if extra:
            base.update(extra)
        return base

    # ═════════════════════════════════════════════════════════════════════════
    # RAMA 1 — DESCUBRIMIENTO
    # ═════════════════════════════════════════════════════════════════════════
    async def descubrir(self, session: aiohttp.ClientSession,
                        tipo: str, genero_id: int,
                        es_animado: bool = False,
                        es_doc: bool = False) -> list:
        url = f"{TMDB_BASE}/discover/{tipo}"

        if tipo == "tv":
            mapeo = {28: 10759, 12: 10759, 878: 10765, 14: 10765,
                     27: 9648, 53: 10768, 10752: 10768}
            genero_id = mapeo.get(genero_id, genero_id)

        generos = [str(genero_id)]
        if es_animado: generos.append("16")
        if es_doc:     generos.append("99")

        params = self._p({
            "sort_by":        "popularity.desc",
            "with_genres":    ",".join(generos),
            "vote_count.gte": 20,
            "page":           1,
        })
        if not es_animado and not es_doc:
            params["without_genres"] = "16"

        data = await self._get(session, url, params)
        res  = data.get("results", [])

        if not res:
            params.pop("without_genres", None)
            params["with_genres"] = str(genero_id)
            data = await self._get(session, url, params)
            res  = data.get("results", [])

        log.info("descubrir(%s, gid=%s) → %d", tipo, genero_id, len(res))
        return res

    # ═════════════════════════════════════════════════════════════════════════
    # RAMA 2 — SIMILITUD (NUEVA VERSIÓN CON SELECCIÓN)
    # ═════════════════════════════════════════════════════════════════════════
    
    async def buscar_titulos(self, session: aiohttp.ClientSession, texto: str) -> list:
        """
        Busca títulos que coincidan con el texto y devuelve una lista de candidatos
        para que el usuario elija.
        """
        url_search = f"{TMDB_BASE}/search/multi"
        candidatos = []
        
        # Buscar en español primero, luego inglés
        for lang in ("es-ES", "en-US"):
            params = {"api_key": self.key, "language": lang,
                      "query": texto, "page": 1, "include_adult": "false"}
            data = await self._get(session, url_search, params)
            raw = [r for r in data.get("results", [])
                   if r.get("media_type") in ("movie", "tv")]
            ids_ya = {c["id"] for c in candidatos}
            for r in raw:
                if r["id"] not in ids_ya:
                    # Añadir información adicional para mostrar
                    titulo = r.get("title") or r.get("name") or "Desconocido"
                    anio = (r.get("release_date") or r.get("first_air_date") or "")[:4]
                    media_type = "🎬 Película" if r.get("media_type") == "movie" else "📺 Serie"
                    r["display_text"] = f"{media_type} • {titulo} ({anio})"
                    candidatos.append(r)
            if candidatos:
                break
        
        log.info("buscar_titulos('%s') → %d resultados", texto, len(candidatos))
        return candidatos[:10]  # Limitar a 10 resultados

    async def recomendar_por_id(self, session: aiohttp.ClientSession,
                                tmdb_id: int, tipo: str) -> dict | None:
        """
        Recomienda contenido similar basado en el ID de una película/serie específica.
        """
        # Obtener detalles de la semilla
        detalles = await self.obtener_detalle(session, tipo, tmdb_id)
        s_titulo = detalles.get("title") or detalles.get("name") or "Desconocido"
        s_anio = (detalles.get("release_date") or detalles.get("first_air_date") or "")[:4]
        
        log.info("Recomendando para: '%s' (%s) id=%s tipo=%s", s_titulo, s_anio, tmdb_id, tipo)
        
        # Obtener keywords de la semilla
        data_kw = await self._get(session, f"{TMDB_BASE}/{tipo}/{tmdb_id}/keywords",
                                  {"api_key": self.key})
        kw_lista = data_kw.get("keywords") or data_kw.get("results") or []
        kw_ids = [str(k["id"]) for k in kw_lista[:8]]
        log.info("Keywords: %s", [k["name"] for k in kw_lista[:8]])
        
        recomendaciones = []
        
        # Discover por keywords
        if kw_ids:
            for kw_chunk in [",".join(kw_ids), "|".join(kw_ids[:4])]:
                params_d = self._p({
                    "with_keywords": kw_chunk,
                    "sort_by": "vote_average.desc",
                    "vote_count.gte": 30,
                    "page": 1,
                    "without_genres": "16",
                })
                data_d = await self._get(session, f"{TMDB_BASE}/discover/{tipo}", params_d)
                pool = [r for r in data_d.get("results", []) if r["id"] != tmdb_id]
                if pool:
                    recomendaciones = pool
                    log.info("Keywords discover → %d resultados", len(pool))
                    break
        
        # Fallback a recommendations
        if len(recomendaciones) < 3:
            data_rec = await self._get(session,
                                       f"{TMDB_BASE}/{tipo}/{tmdb_id}/recommendations",
                                       self._p({"page": 1}))
            ids_ya = {r["id"] for r in recomendaciones}
            for r in data_rec.get("results", []):
                if r["id"] not in ids_ya and r["id"] != tmdb_id:
                    recomendaciones.append(r)
            log.info("Tras fallback: %d total", len(recomendaciones))
        
        if not recomendaciones:
            log.warning("Sin recomendaciones para '%s'", s_titulo)
            return None
        
        top3 = sorted(recomendaciones,
                      key=lambda x: x.get("vote_average", 0), reverse=True)[:3]
        
        return {
            "semilla": {"titulo": s_titulo, "anio": s_anio, "tipo": tipo, "id": tmdb_id},
            "recomendaciones": top3,
            "tipo": tipo,
        }

    # ═════════════════════════════════════════════════════════════════════════
    # RAMA 3 — TALENTO
    # ═════════════════════════════════════════════════════════════════════════
    async def buscar_persona(self, session: aiohttp.ClientSession,
                             nombre: str) -> list:
        url = f"{TMDB_BASE}/search/person"

        data = await self._get(session, url, self._p({
            "query": nombre, "page": 1, "include_adult": "false"
        }))
        res = data.get("results", [])

        if len(res) < 2:
            params_en = {"api_key": self.key, "language": "en-US",
                         "query": nombre, "page": 1, "include_adult": "false"}
            data_en = await self._get(session, url, params_en)
            ids_ya  = {r["id"] for r in res}
            for r in data_en.get("results", []):
                if r["id"] not in ids_ya:
                    res.append(r)

        log.info("buscar_persona('%s') → %d", nombre, len(res))
        return res[:5]

    async def descubrir_por_actor_y_genero(self, session: aiohttp.ClientSession,
                                           person_id: int,
                                           genero_id: int) -> list:
        url    = f"{TMDB_BASE}/discover/movie"
        params = self._p({
            "with_cast":      str(person_id),
            "with_genres":    str(genero_id),
            "sort_by":        "vote_average.desc",
            "vote_count.gte": 50,
            "page":           1,
        })
        data = await self._get(session, url, params)
        res  = data.get("results", [])

        if not res:
            del params["vote_count.gte"]
            params["sort_by"] = "popularity.desc"
            data = await self._get(session, url, params)
            res  = data.get("results", [])

        log.info("actor+genero(pid=%s, gid=%s) → %d", person_id, genero_id, len(res))
        return res

    # ═════════════════════════════════════════════════════════════════════════
    # DETALLE COMPLETO
    # ═════════════════════════════════════════════════════════════════════════
    async def obtener_detalle(self, session: aiohttp.ClientSession,
                              tipo: str, tmdb_id: int) -> dict:
        url    = f"{TMDB_BASE}/{tipo}/{tmdb_id}"
        params = self._p({"append_to_response": "credits,release_dates,content_ratings"})
        return await self._get(session, url, params)

    # ═════════════════════════════════════════════════════════════════════════
    # RATINGS — OMDb
    # ═════════════════════════════════════════════════════════════════════════
    async def ratings_omdb(self, session: aiohttp.ClientSession,
                           titulo_original: str,
                           titulo_es: str = "",
                           anio: str = "") -> str:
        async def _q(t: str, y: str = "") -> dict | None:
            for omdb_type in ("movie", "series"):
                p = {"apikey": self.omdb, "t": t, "type": omdb_type}
                if y:
                    p["y"] = y
                try:
                    async with session.get(OMDB_BASE, params=p) as r:
                        if r.status == 200:
                            d = await r.json(content_type=None)
                            if d.get("Response") == "True":
                                return d
                except Exception as e:
                    log.warning("OMDb '%s': %s", t, e)
            return None

        titulos = [(titulo_original, anio), (titulo_original, "")]
        if titulo_es and titulo_es.lower() != titulo_original.lower():
            titulos += [(titulo_es, anio), (titulo_es, "")]

        data = None
        for t, y in titulos:
            data = await _q(t, y)
            if data:
                break

        if not data:
            return "⭐ Ratings no disponibles"

        imdb  = data.get("imdbRating", "N/A")
        votos = data.get("imdbVotes", "")
        rt    = next((r["Value"] for r in data.get("Ratings", [])
                      if r["Source"] == "Rotten Tomatoes"), "N/A")
        v_str = f" ({votos} votos)" if votos and votos != "N/A" else ""
        return f"⭐ IMDb: `{imdb}`{v_str} | 🍅 RT: `{rt}`"

    # ═════════════════════════════════════════════════════════════════════════
    # TARJETA COMPLETA
    # ═════════════════════════════════════════════════════════════════════════
    async def construir_tarjeta(self, session: aiohttp.ClientSession,
                                item: dict, tipo: str = "movie") -> dict:
        d        = await self.obtener_detalle(session, tipo, item["id"])
        titulo   = d.get("title") or d.get("name") or "Desconocido"
        tit_orig = d.get("original_title") or d.get("original_name") or titulo
        anio     = (d.get("release_date") or d.get("first_air_date") or "")[:4]
        generos  = " · ".join(g["name"] for g in d.get("genres", [])) or "N/A"
        cast     = d.get("credits", {}).get("cast", [])
        actores  = ", ".join(a["name"] for a in cast[:4]) or "N/A"
        crew     = d.get("credits", {}).get("crew", [])
        director = next((p["name"] for p in crew if p.get("job") == "Director"), None)
        runtime  = d.get("runtime") or (d.get("episode_run_time") or [None])[0]
        temporadas = d.get("number_of_seasons")
        score    = d.get("vote_average", 0)
        desc     = d.get("overview") or "Sin descripción disponible."
        poster   = d.get("poster_path")
        edad     = _clasificacion(d, tipo)
        ratings  = await self.ratings_omdb(session, tit_orig, titulo, anio)
        url_yt   = ("https://www.youtube.com/results?search_query="
                    + f"{tit_orig} official trailer".replace(" ", "+"))

        L = [f"🎬 *{titulo.upper()}*"]
        if tit_orig.lower() != titulo.lower():
            L.append(f"_({tit_orig})_")
        L.append("")
        L.append(f"📅 {anio}  |  {generos}")

        extras = []
        if runtime:    extras.append(f"⏱️ {runtime} min")
        if temporadas: extras.append(f"📺 {temporadas} temp.")
        if edad:       extras.append(f"🔞 {edad}")
        if extras:     L.append("  ".join(extras))

        L += ["", ratings, f"🌟 TMDB: `{score:.1f}/10`", "",
              f"🎭 *Reparto:* {actores}"]
        if director:
            L.append(f"🎥 *Director:* {director}")
        L += ["", f"📝 _{desc[:380]}{'...' if len(desc) > 380 else ''}_"]

        return {
            "texto":      "\n".join(L),
            "poster_url": f"{IMG_BASE}{poster}" if poster else None,
            "url_yt":     url_yt,
        }


def _clasificacion(d: dict, tipo: str) -> str | None:
    if tipo == "movie":
        for e in d.get("release_dates", {}).get("results", []):
            if e.get("iso_3166_1") in ("MX", "ES", "US"):
                for rd in e.get("release_dates", []):
                    c = rd.get("certification", "").strip()
                    if c:
                        return c
    else:
        for e in d.get("content_ratings", {}).get("results", []):
            if e.get("iso_3166_1") in ("MX", "ES", "US"):
                r = e.get("rating", "").strip()
                if r:
                    return r
    return None