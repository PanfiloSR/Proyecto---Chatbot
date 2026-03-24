# movie_engine.py
import aiohttp
from config import TMDB_API_KEY

class MovieEngine:
    def __init__(self):
        self.api_key = TMDB_API_KEY
        self.base_url = "https://api.themoviedb.org/3"

    async def descubrir_contenido(self, session, tipo, genero_id, es_animado, es_doc=False):
        url = f"{self.base_url}/discover/{tipo}"
        
        # Construcción de la lista de géneros
        lista_generos = [str(genero_id)]
        
        if es_doc:
            lista_generos.append("99") # Obligamos a que sea Documental
        if es_animado:
            lista_generos.append("16") # Obligamos a que sea Animación

        params = {
            'api_key': self.api_key,
            'language': 'es-ES',
            'sort_by': 'popularity.desc',
            'with_genres': ",".join(lista_generos),
            'page': 1,
            'vote_count.gte': 100 # Filtramos para que salgan cosas de calidad
        }
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            return data.get('results', [])