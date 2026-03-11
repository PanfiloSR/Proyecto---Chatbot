# database.py
import sqlite3
import asyncio

class MovieDB:
    def __init__(self):
        self.lock = asyncio.Lock() # Mecanismo de Sincronización
        self._setup()

    def _setup(self):
        with sqlite3.connect("bot_cine.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT, consultas INTEGER)")

    async def registrar_usuario(self, user_id, nombre):
        """Acceso controlado al recurso compartido (Base de Datos)"""
        async with self.lock:
            with sqlite3.connect("bot_cine.db") as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO usuarios VALUES (?, ?, 0)", (user_id, nombre))
                cursor.execute("UPDATE usuarios SET consultas = consultas + 1 WHERE id = ?", (user_id,))
                conn.commit()