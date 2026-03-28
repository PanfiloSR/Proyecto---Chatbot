"""
Ejecuta este script primero para diagnosticar la conexión:
    python test_tmdb.py
"""
import asyncio
import aiohttp
import sys

# ── Carga manual de config para verificar que las keys existen ───────────────
try:
    from config import TMDB_API_KEY, OMDB_API_KEY
    print(f"✅ TMDB_API_KEY cargada: {'*' * (len(TMDB_API_KEY)-4) + TMDB_API_KEY[-4:]}")
    print(f"✅ OMDB_API_KEY cargada: {'*' * (len(OMDB_API_KEY)-4) + OMDB_API_KEY[-4:]}")
except Exception as e:
    print(f"❌ Error cargando config.py: {e}")
    sys.exit(1)

if not TMDB_API_KEY or TMDB_API_KEY == "TU_KEY_AQUI":
    print("❌ TMDB_API_KEY está vacía o sin configurar")
    sys.exit(1)

async def test():
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:

        # Test 1: Buscar persona
        print("\n─── TEST 1: buscar_persona 'Pedro Pascal' ───")
        url = "https://api.themoviedb.org/3/search/person"
        params = {"api_key": TMDB_API_KEY, "language": "es-ES",
                  "query": "Pedro Pascal", "page": 1}
        async with session.get(url, params=params) as r:
            print(f"Status: {r.status}")
            data = await r.json(content_type=None)
            res = data.get("results", [])
            print(f"Resultados: {len(res)}")
            for p in res[:3]:
                print(f"  → {p['name']} (id={p['id']})")

        # Test 2: Buscar título
        print("\n─── TEST 2: buscar_titulo 'Inception' ───")
        url2 = "https://api.themoviedb.org/3/search/multi"
        params2 = {"api_key": TMDB_API_KEY, "language": "es-ES",
                   "query": "Inception", "page": 1}
        async with session.get(url2, params=params2) as r:
            print(f"Status: {r.status}")
            data2 = await r.json(content_type=None)
            res2 = [x for x in data2.get("results", [])
                    if x.get("media_type") in ("movie", "tv")]
            print(f"Resultados: {len(res2)}")
            for m in res2[:3]:
                print(f"  → {m.get('title') or m.get('name')} ({m.get('media_type')})")

        # Test 3: OMDb
        print("\n─── TEST 3: OMDb ratings 'Inception' ───")
        url3 = "http://www.omdbapi.com/"
        params3 = {"apikey": OMDB_API_KEY, "t": "Inception", "type": "movie"}
        async with session.get(url3, params=params3) as r:
            print(f"Status: {r.status}")
            data3 = await r.json(content_type=None)
            print(f"Response: {data3.get('Response')}")
            print(f"IMDb: {data3.get('imdbRating')}")
            rt = next((x["Value"] for x in data3.get("Ratings", [])
                       if x["Source"] == "Rotten Tomatoes"), "N/A")
            print(f"RT: {rt}")

asyncio.run(test())