# main.py

import asyncio
from services.mqtt.mqtt_handler import MQTTHandler
from services.openai.realtime import OpenAIRealtimeClient

def main():
    # 1. Connect to your Mosquitto broker
    mqtt = MQTTHandler(host="192.168.1.251", port=1885)
    
    # 2. Create the realtime client, injecting the MQTT handler as dispatcher
    client = OpenAIRealtimeClient(dispatcher=mqtt)
    asyncio.run(client.connect())
    # 3. Run the realtime loop
    try:
        asyncio.run(client.connect())
    except KeyboardInterrupt:
        print("🛑 Stopped by user")
    finally:
        client.close()

if __name__ == "__main__":
    main()
