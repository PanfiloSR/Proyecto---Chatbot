# test_fixed.py
import requests
import time
from config import TELEGRAM_TOKEN
import urllib3
urllib3.disable_warnings()

TOKEN = TELEGRAM_TOKEN
BASE = f"https://api.telegram.org/bot{TOKEN}"

# Configurar sesión con timeouts más largos y keep-alive
session = requests.Session()
session.timeout = (30, 60)  # (connect timeout, read timeout)
session.keep_alive = True

print("=" * 60)
print("TEST CON TIME OUTS CORREGIDOS")
print("=" * 60)

# Obtener chat_id
response = session.get(f"{BASE}/getUpdates", params={"limit": 10}, timeout=30)
data = response.json()

chat_id = None
for update in data.get("result", []):
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        break

if not chat_id:
    print("❌ Envía /start al bot primero")
    exit()

print(f"✅ Chat ID: {chat_id}")

# Enviar mensaje con botón
keyboard = {"inline_keyboard": [[{"text": "🔘 HAZ CLIC AQUÍ", "callback_data": "test"}]]}

response = session.post(f"{BASE}/sendMessage", json={
    "chat_id": chat_id,
    "text": "🔘 HAZ CLIC EN EL BOTÓN ABAJO",
    "reply_markup": keyboard
}, timeout=30)

print("✅ Botón enviado. Esperando callback...")
print("👉 HAZ CLIC EN EL BOTÓN AHORA\n")

# Monitorear con timeouts largos
last_update_id = 0
start_time = time.time()
timeout = 30  # 30 segundos de espera

while time.time() - start_time < timeout:
    try:
        response = session.get(f"{BASE}/getUpdates", params={
            "timeout": 10,  # Long polling timeout
            "offset": last_update_id + 1
        }, timeout=15)  # Timeout total de 15 segundos
        
        if response.status_code == 200:
            data = response.json()
            if data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"]
                    
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        print("\n" + "🎉" * 20)
                        print("✅ ¡CALLBACK RECIBIDO!")
                        print(f"Datos: {callback['data']}")
                        print("🎉" * 20)
                        
                        # Responder
                        session.post(f"{BASE}/answerCallbackQuery", json={
                            "callback_query_id": callback["id"],
                            "text": "¡Recibido!"
                        }, timeout=10)
                        
                        print("\n✅ ¡EL BOT FUNCIONA CORRECTAMENTE!")
                        print("El problema era el timeout de conexión.")
                        exit(0)
                    
                    elif "message" in update:
                        print(f"📝 Mensaje: {update['message'].get('text', '')}")
        
        time.sleep(0.5)
        
    except requests.exceptions.Timeout:
        print("⏳ Timeout, reintentando...")
        continue
    except Exception as e:
        print(f"Error: {e}")
        continue

print("\n❌ No se recibió callback")
print("Posible solución: Verifica tu conexión a internet o firewall")