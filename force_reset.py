# force_reset.py
import requests
from config import TELEGRAM_TOKEN

TOKEN = TELEGRAM_TOKEN
BASE = f"https://api.telegram.org/bot{TOKEN}"

print("Forzando reset del bot...")

# 1. Eliminar webhook
print("1. Eliminando webhook...")
response = requests.post(f"{BASE}/deleteWebhook", json={"drop_pending_updates": True})
print(f"   Resultado: {response.json()}")

# 2. Obtener información del webhook
print("\n2. Verificando webhook...")
response = requests.get(f"{BASE}/getWebhookInfo")
print(f"   Webhook info: {response.json()}")

# 3. Probar conexión
print("\n3. Probando conexión...")
response = requests.get(f"{BASE}/getMe")
print(f"   Bot info: {response.json()}")

print("\n✅ Reset completado")
print("Ahora ejecuta test_simple_callback.py nuevamente")