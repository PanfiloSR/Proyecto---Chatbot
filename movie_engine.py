# movie_engine.py
import aiohttp
from config import TMDB_API_KEY

class MovieEngine:
    def __init__(self):
        self.api_key = TMDB_API_KEY
        self.base_url = "https://api.themoviedb.org/3"

    async def buscar_item(self, session, nombre, tipo):
        url = f"{self.base_url}/search/{tipo}"
        params = {'api_key': self.api_key, 'query': nombre, 'language': 'es-ES'}
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            return data['results'][0] if data.get('results') else None

    async def obtener_muchas_recs(self, session, item_id, tipo):
        """Trae más resultados para tener de dónde filtrar"""
        url = f"{self.base_url}/{tipo}/{item_id}/recommendations"
        params = {'api_key': self.api_key, 'language': 'es-ES'}
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            return data.get('results', []) # Traemos los 20 resultados de la primera página