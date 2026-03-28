# movie_engine.py
import aiohttp
import logging
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
# Crear sesión HTTP — se usa con "async with crear_sesion() as session:"
# ─────────────────────────────────────────────────────────────────────────────
def crear_sesion() -> aiohttp.ClientSession:
    """
    Devuelve una ClientSession lista para usar con 'async with'.
    aiohttp.ClientSession ya implementa __aenter__ / __aexit__.
    """
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
        log.info("MovieEngine inicializado. TMDB key: ...%s", self.key[-4:])

    # ── GET helper ────────────────────────────────────────────────────────────
    async def _get(self, session: aiohttp.ClientSession,
                   url: str, params: dict) -> dict:
        try:
            async with session.get(url, params=params) as r:
                body = await r.text()
                log.debug("GET %s → %s | %d bytes", url, r.status, len(body))
                if r.status == 200:
                    import json
                    return json.loads(body)
                log.warning("TMDB %s status=%s cuerpo=%s", url, r.status, body[:300])
        except aiohttp.ServerTimeoutError:
            log.error("Timeout en GET %s", url)
        except aiohttp.ClientConnectorError as e:
            log.error("Sin conexión para GET %s: %s", url, e)
        except Exception as e:
            log.error("Error inesperado GET %s: %s", url, e, exc_info=True)
        return {}

    def _p(self, extra: dict | None = None) -> dict:
        """Parámetros base TMDB: api_key + idioma español."""
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

        log.info("descubrir(%s, gid=%s) → %d resultados", tipo, genero_id, len(res))
        return res

    # ═════════════════════════════════════════════════════════════════════════
    # RAMA 2 — SIMILITUD
    # ═════════════════════════════════════════════════════════════════════════
    async def buscar_titulo(self, session: aiohttp.ClientSession,
                            texto: str) -> list:
        """
        Busca en /search/multi.
        Intenta primero en español; si hay menos de 3 resultados,
        repite en inglés (útil para títulos originales).
        """
        url = f"{TMDB_BASE}/search/multi"

        # --- intento 1: español ---
        data = await self._get(session, url, self._p({
            "query": texto, "page": 1, "include_adult": "false"
        }))
        res = [r for r in data.get("results", [])
               if r.get("media_type") in ("movie", "tv")]

        # --- intento 2: inglés (para títulos originales) ---
        if len(res) < 3:
            params_en = {"api_key": self.key, "language": "en-US",
                         "query": texto, "page": 1, "include_adult": "false"}
            data_en = await self._get(session, url, params_en)
            ids_ya  = {r["id"] for r in res}
            for r in data_en.get("results", []):
                if r.get("media_type") in ("movie", "tv") and r["id"] not in ids_ya:
                    res.append(r)

        log.info("buscar_titulo('%s') → %d candidatos", texto, len(res))
        return res[:6]

    async def obtener_recomendaciones(self, session: aiohttp.ClientSession,
                                      tipo: str, tmdb_id: int) -> list:
        params = self._p({"page": 1})
        data_r = await self._get(session, f"{TMDB_BASE}/{tipo}/{tmdb_id}/recommendations", params)
        res    = data_r.get("results", [])

        if len(res) < 5:
            data_s = await self._get(session, f"{TMDB_BASE}/{tipo}/{tmdb_id}/similar", params)
            ids    = {r["id"] for r in res}
            for r in data_s.get("results", []):
                if r["id"] not in ids:
                    res.append(r)

        log.info("recomendaciones(%s, %s) → %d", tipo, tmdb_id, len(res))
        return res

    # ═════════════════════════════════════════════════════════════════════════
    # RAMA 3 — TALENTO
    # ═════════════════════════════════════════════════════════════════════════
    async def buscar_persona(self, session: aiohttp.ClientSession,
                             nombre: str) -> list:
        """
        /search/person — prueba español e inglés para mayor cobertura.
        """
        url = f"{TMDB_BASE}/search/person"

        # intento 1: español
        data = await self._get(session, url, self._p({
            "query": nombre, "page": 1, "include_adult": "false"
        }))
        res = data.get("results", [])

        # intento 2: inglés
        if len(res) < 2:
            params_en = {"api_key": self.key, "language": "en-US",
                         "query": nombre, "page": 1, "include_adult": "false"}
            data_en = await self._get(session, url, params_en)
            ids_ya  = {r["id"] for r in res}
            for r in data_en.get("results", []):
                if r["id"] not in ids_ya:
                    res.append(r)

        log.info("buscar_persona('%s') → %d resultados", nombre, len(res))
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
    # DETALLE COMPLETO DE UNA OBRA
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
        """
        Hasta 4 intentos: original+año → original → español+año → español.
        """
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
                    log.warning("OMDb error '%s': %s", t, e)
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
        d = await self.obtener_detalle(session, tipo, item["id"])

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