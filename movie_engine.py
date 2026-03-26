# movie_engine.py
import aiohttp
from config import TMDB_API_KEY, OMDB_API_KEY

class MovieEngine:
    def __init__(self):
        self.api_key = TMDB_API_KEY
        self.omdb_key = OMDB_API_KEY # Tu key c28e398f configurada en config.py
        self.base_url = "https://api.themoviedb.org/3"
        self.base_omdb = "http://www.omdbapi.com/"


    async def descubrir_contenido(self, session, tipo, genero_id, es_animado, es_doc=False):
        url = f"{self.base_url}/discover/{tipo}"

        if tipo == 'tv':
            mapeo_tv = {
                27: 9648,   
                878: 10765,
                28: 10759,  
            }
            genero_id = mapeo_tv.get(genero_id, genero_id)
        
        if tipo == 'tv':
            mapeo_tv = {878: 10765, 28: 10759, 12: 10759}
            genero_id = mapeo_tv.get(genero_id, genero_id)

        lista_generos = [str(genero_id)]
        if es_doc: lista_generos.append("99")
        if es_animado: lista_generos.append("16")

        params = {
            'api_key': self.api_key,
            'language': 'es-ES',
            'sort_by': 'popularity.desc',
            'with_genres': ",".join(lista_generos),
            'page': 1,
            'vote_count.gte': 5 
        }

        if not es_animado and not es_doc:
            params['without_genres'] = "16"

        async with session.get(url, params=params) as resp:
            data = await resp.json()
            resultados = data.get('results', [])

            if not resultados:
                params.pop('without_genres', None)
                params['with_genres'] = str(genero_id)
                async with session.get(url, params=params) as retry_resp:
                    data_retry = await retry_resp.json()
                    resultados = data_retry.get('results', [])

            return resultados

    async def obtener_ratings_omdb(self, session, titulo):
        """Consulta ratings de IMDb y Rotten Tomatoes usando tu key c28e398f"""
        params = {
            'apikey': self.omdb_key,
            't': titulo
        }
        try:
            async with session.get(self.base_omdb, params=params) as resp:
                data = await resp.json()
                if data.get('Response') == 'True':
                    imdb = data.get('imdbRating', 'N/A')
                    rt = "N/A"
                    for r in data.get('Ratings', []):
                        if r['Source'] == 'Rotten Tomatoes':
                            rt = r['Value']
                    return f"⭐ IMDb: `{imdb}` | 🍅 Rotten: `{rt}`"
                return "⭐ Ratings: `No disponibles`"
        except:
            return "⭐ Ratings: `Consultando...`"