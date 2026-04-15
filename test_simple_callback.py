# test_simple_callback.py
import requests
import time
from config import TELEGRAM_TOKEN

TOKEN = TELEGRAM_TOKEN
BASE = f"https://api.telegram.org/bot{TOKEN}"

print("=" * 60)
print("TEST DE CALLBACKS - Versión Simple")
print("=" * 60)

# Paso 1: Obtener el chat_id de tu último mensaje
print("\n1️⃣ Obteniendo tu chat_id...")
response = requests.get(f"{BASE}/getUpdates", params={"limit": 10})
data = response.json()

chat_id = None
if data.get("result"):
    for update in data["result"]:
        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            print(f"   ✅ Chat ID encontrado: {chat_id}")
            break

if not chat_id:
    print("   ❌ No se encontró chat_id. Envía /start a tu bot y vuelve a ejecutar.")
    exit()

# Paso 2: Enviar mensaje con botón
print("\n2️⃣ Enviando mensaje con botón...")
keyboard = {
    "inline_keyboard": [
        [{"text": "🔘 HAZ CLIC AQUÍ", "callback_data": "test_data"}]
    ]
}

response = requests.post(f"{BASE}/sendMessage", json={
    "chat_id": chat_id,
    "text": "🤖 Prueba de callback - Haz clic en el botón:",
    "reply_markup": keyboard
})

if response.status_code == 200:
    print("   ✅ Mensaje enviado correctamente")
    print("   👉 AHORA haz clic en el botón en Telegram")
else:
    print(f"   ❌ Error: {response.text}")
    exit()

# Paso 3: Monitorear callbacks por 20 segundos
print("\n3️⃣ Esperando callback (20 segundos)...")
print("   (Presiona Ctrl+C para cancelar)\n")

start_time = time.time()
last_update_id = 0

while time.time() - start_time < 20:
    try:
        # Obtener updates
        response = requests.get(f"{BASE}/getUpdates", params={
            "timeout": 2,
            "offset": last_update_id + 1
        }, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"]
                    
                    # Verificar si es callback
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        print("\n" + "=" * 60)
                        print("🎉 ¡CALLBACK RECIBIDO! 🎉")
                        print("=" * 60)
                        print(f"📊 Datos del callback:")
                        print(f"   - Data: {callback['data']}")
                        print(f"   - Usuario: {callback['from']['first_name']}")
                        print(f"   - ID: {callback['id']}")
                        
                        # Responder al callback
                        answer_response = requests.post(f"{BASE}/answerCallbackQuery", json={
                            "callback_query_id": callback["id"],
                            "text": "¡Callback recibido correctamente!",
                            "show_alert": False
                        })
                        
                        if answer_response.status_code == 200:
                            print(f"   ✅ Respuesta enviada a Telegram")
                        else:
                            print(f"   ❌ Error al responder: {answer_response.text}")
                        
                        # Editar mensaje para confirmar
                        msg = callback["message"]
                        requests.post(f"{BASE}/editMessageText", json={
                            "chat_id": msg["chat"]["id"],
                            "message_id": msg["message_id"],
                            "text": f"✅ ¡Funciona! Recibiste: {callback['data']}\n\nEnvía /start para otra prueba"
                        })
                        
                        print("=" * 60)
                        print("✅ Prueba exitosa! El bot puede recibir callbacks.")
                        print("=" * 60)
                        exit(0)
                    
                    # Verificar mensajes de texto
                    elif "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        print(f"\n📝 Mensaje recibido: '{msg['text']}'")
        
        time.sleep(0.5)
        
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)

print("\n⏰ Tiempo agotado - No se recibió ningún callback.")
print("❌ El problema persiste: Telegram no envía los callbacks.")