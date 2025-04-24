# services/mqtt_handler.py

import asyncio
import paho.mqtt.client as mqtt

class MQTTHandler:
    """
    Dispatches smart‑home commands to an ESP32 via MQTT.
    """

    def __init__(self, host="192.168.1.251", port=1885):
        # Connect to your Mosquitto broker
        self.client = mqtt.Client()
        self.client.connect(host, port)
        # Start the network loop in a background thread
        self.client.loop_start()

    async def dispatch(self, command: dict):
        """
        Publish one or more MQTT messages based on the command dict.
        Expects command["target"] to be str or list of str.
        """
        action = command.get("action")          # "turn_on" or "turn_off"
        device = command.get("device")          # "lights"
        targets = command.get("target")
        if isinstance(targets, str):
            targets = [targets]

        for color in targets:
            topic = f"{device}/{color}"        # e.g. "lights/red"
            payload = "ON" if action == "turn_on" else "OFF"
            self.client.publish(topic, payload)
            print(f"🔌 MQTT → topic='{topic}', payload='{payload}'")
            # yield back to the event loop
            await asyncio.sleep(0)
