# test_complete.py
import requests
import time
from config import TELEGRAM_TOKEN

TOKEN = TELEGRAM_TOKEN
BASE = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = 0

def send_start_menu(chat_id):
    """Envía el menú con botones"""
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔘 Test Button 1", "callback_data": "test1"}],
            [{"text": "🔘 Test Button 2", "callback_data": "test2"}]
        ]
    }
    
    response = requests.post(f"{BASE}/sendMessage", json={
        "chat_id": chat_id,
        "text": "🤖 Bot de prueba - Haz clic en un botón:",
        "reply_markup": keyboard
    })
    
    if response.status_code == 200:
        print("✅ Menú enviado correctamente")
    else:
        print(f"❌ Error enviando menú: {response.text}")

print("🔍 Bot iniciado - Envía /start para recibir el menú")
print("="*50)

while True:
    try:
        # Obtener updates
        params = {"timeout": 30, "offset": last_update_id + 1}
        response = requests.get(f"{BASE}/getUpdates", params=params, timeout=35)
        data = response.json()
        
        if data.get("ok") and data.get("result"):
            for update in data["result"]:
                last_update_id = update["update_id"]
                
                # Procesar mensajes /start
                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    
                    print(f"\n📝 Mensaje recibido: '{text}' de {msg['from']['first_name']}")
                    
                    if text == "/start":
                        print("🎯 Enviando menú con botones...")
                        send_start_menu(chat_id)
                
                # Procesar callbacks (clics en botones)
                if "callback_query" in update:
                    callback = update["callback_query"]
                    data_cb = callback["data"]
                    chat_id = callback["message"]["chat"]["id"]
                    message_id = callback["message"]["message_id"]
                    
                    print(f"\n🎯 ¡CALLBACK RECIBIDO!")
                    print(f"   Botón presionado: {data_cb}")
                    print(f"   Usuario: {callback['from']['first_name']}")
                    
                    # Responder al callback (importante!)
                    requests.post(f"{BASE}/answerCallbackQuery", json={
                        "callback_query_id": callback["id"],
                        "text": f"Recibido: {data_cb}"
                    })
                    
                    # Editar el mensaje para confirmar
                    requests.post(f"{BASE}/editMessageText", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": f"✅ ¡Funciona! Presionaste: {data_cb}\n\nEnvía /start para probar de nuevo"
                    })
                    
                    print("   ✅ Respuesta enviada")
        
        time.sleep(0.5)
        
    except KeyboardInterrupt:
        print("\n👋 Deteniendo...")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(2)