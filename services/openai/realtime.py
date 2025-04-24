import os
import asyncio
import json
import requests
import websockets
import base64
import sounddevice as sd
import paho.mqtt.client as mqtt
from typing import Any
from websockets.client import connect
from dotenv import load_dotenv

from utils.microphone import Microphone
from utils.response_parser import ResponseParser
from services.openai.schema import smart_home_command_schema

class OpenAIRealtimeClient:
    """
    Handles real-time audio streaming to OpenAI’s GPT‑4o Realtime API,
    then forwards each assistant response (with its transcript) to the
    ResponseParser for validation, fallback, and dispatch.
    """

    def __init__(self, dispatcher=None):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.session = None
        self.client_secret = None
        self.websocket_url = "wss://api.openai.com/v1/realtime"
        self.last_transcript = None
        self._json_buffer: str = ""
        self.parser = ResponseParser(dispatcher=dispatcher)
        
        self.MQTT_BROKER = "test.mosquitto.org"
        self.MQTT_PORT   = 1883
        self.MQTT_TOPIC  = "voice/commands"
            
        self.audio_out = sd.RawOutputStream(
            samplerate=16000, 
            channels=1,
            dtype='int16',
            latency='low',
        )
        
        self.audio_out.start()


    def publish_payload(self, payload: dict):
        """
        Connects to the public Mosquitto broker and publishes the JSON payload
        to topic 'voice/commands'.
        """
        client = mqtt.Client()
        client.connect(self.MQTT_BROKER, self.MQTT_PORT, keepalive=60)
        # turn dict into compact JSON
        message = json.dumps(payload, separators=(",", ":"))
        client.publish(self.MQTT_TOPIC,
                    json.dumps(payload, separators=(",", ":")))
        client.disconnect()
        
    def _build_instructions(self) -> str:
        schema_json = json.dumps(smart_home_command_schema, indent=2)
        return (
            "You must respond with a single valid JSON object that conforms to the following schema:\n\n"
            f"{schema_json}\n\n"
            "If the command is generally about the lights, add all lights to the to the array to turn off or on. If the command is entirely unclear, set `command` to null and clarify in the `speak` field.\n"
            "Do not include any explanation, markdown, or unstructured output — only JSON matching this schema."
        )

    def create_session(self):
        url = "https://api.openai.com/v1/realtime/sessions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "realtime=v1"
        }
        payload = {
            "model": "gpt-4o-realtime-preview",
            # <- include audio here so the WS will send you audio.delta frames
            "modalities": ["audio", "text"],
            "instructions": self._build_instructions(),
            "voice": "alloy",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {"model": "whisper-1"}
        }

        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        self.session       = data
        self.client_secret = data["client_secret"]["value"]
        return data

    async def connect(self):
        # 1) Lazily create a session if we don’t have one yet
        if not self.client_secret:
            self.create_session()

        # 2) Build the WS URL with session_id
        socket_url = f"{self.websocket_url}?session_id={self.session['id']}"

        extra_headers = {
            "Authorization": f"Bearer {self.client_secret}",
            "OpenAI-Beta": "realtime=v1",
        }

        # 3) Open the socket and drive our producer/consumer
        async with connect(
            socket_url,
            extra_headers=extra_headers,
            ping_interval=60,
            ping_timeout=60,
        ) as ws:

            # start streaming mic → API and API → speaker in parallel
            producer = asyncio.create_task(self._stream_audio(ws))
            consumer = asyncio.create_task(self._handle_responses(ws))

            done, pending = await asyncio.wait(
                [producer, consumer],
                return_when=asyncio.FIRST_EXCEPTION,
            )

            # if one of them errors, cancel the other
            for task in pending:
                task.cancel()

            # log any exception
            for task in done:
                if task.exception():
                    print(f"❌ Task failed: {task.exception()}")
                else:
                    print("✅ Task completed successfully")
         
    async def _stream_audio(self, ws: websockets.WebSocketClientProtocol):
        mic = Microphone()
        queue: asyncio.Queue[bytes] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        # callback for your blocking mic.stream
        def enqueue(chunk: bytes):
            loop.call_soon_threadsafe(queue.put_nowait, chunk)

        # start capturing audio on a thread
        producer = loop.run_in_executor(None, mic.stream, enqueue)

        try:
            # for every chunk produced by mic.stream…
            while True:
                chunk = await queue.get()
                # base64‐encode it:
                audio_b64 = base64.b64encode(chunk).decode("ascii")
                # send the required JSON message
                await ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                }))
        except websockets.ConnectionClosed as e:
            print(f"🔌 Stream task noticed closed socket: {e.code} {e.reason}")
        finally:
            # once mic.stream exits or you break out, commit the buffer
            try:
                await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            except Exception:
                pass
            producer.cancel()
            
            

    def is_valid_json(self, raw: str) -> bool:
        # 1) Trim off any accidental leading/trailing whitespace
        cleaned = raw.strip()
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # 2) Show exactly what we received and where it blew up
            print(f"❌ Malformed JSON buffer (line {e.lineno}, col {e.colno} – {e.msg}):")
            print(repr(cleaned))
            return False

        # 3) Quick schema check
        if (
            isinstance(obj, dict)
            and "speak" in obj and isinstance(obj["speak"], str)
            and "command" in obj and (obj["command"] is None or isinstance(obj["command"], dict))
        ):
            # 4) POC: push straight into MQTT
            self.publish_payload(obj)
            return True

        print("❌ JSON didn’t match our expected schema:")
        print(repr(cleaned))
        return False
    
    
    def validate_payload(self, payload: dict) -> bool:
        """
        Ensure the payload matches your expected structure:
          { "speak": str, "command": {action,device,target} | None }
        """
        if not isinstance(payload, dict):
            return False

        # must have both keys
        if "speak" not in payload or "command" not in payload:
            return False

        if not isinstance(payload["speak"], str):
            return False

        cmd = payload["command"]
        # command may be null
        if cmd is None:
            return True

        # or a dict with 3 required keys
        if not isinstance(cmd, dict):
            return False
        required = {"action", "device", "target"}
        if not required.issubset(cmd.keys()):
            return False

        # you can add more type/enum checks here if you like
        return True
    
    
            # TODO: This needs to be piped into the parser, this is a debug function and will need to be rewritten for any functionality
    async def _handle_responses(self, ws):
        async for raw in ws:
            msg = json.loads(raw)
            msg_type = msg.get("type")
            print(f"⮞ got message type: {msg_type}")

            # ——————————————————————————————
            # 1) Capture the JSON text *fragments*:
            if msg_type == "response.content_part.delta":
                frag = msg.get("content", "")
                print("   🔔 JSON delta:", repr(frag))
                self._json_buffer += frag

            # 1b) …and the *final* JSON fragment, if any…
            elif msg_type == "response.content_part.done":
                # some sessions only send the last chunk here
                frag = msg.get("content", "")
                print("   ✅ JSON final fragment:", repr(frag))
                self._json_buffer += frag

            # ——————————————————————————————
            # 2) When the entire response is done, parse:
            elif msg_type == "response.done":
                if not self._json_buffer:
                    print("❌ JSON buffer is empty—no content_part was ever added")
                else:
                    try:
                        payload = json.loads(self._json_buffer)
                    except Exception as e:
                        print("❌ JSON parse failed:", e)
                        print("Buffer was:", repr(self._json_buffer))
                    else:
                        print("✅ Parsed payload:", payload)
                        self.publish_payload(payload)

                # reset for the next turn
                self._json_buffer = ""

            # ——————————————————————————————
            # # 3) Audio playback (base64)
            # elif msg_type == "response.audio.delta":
            #     raw = msg.get("audio") or msg.get("data") or msg.get("delta")
            #     if isinstance(raw, str):
            #         chunk = None
            #         try:
            #             chunk = base64.b64decode(raw.strip())
            #         except Exception:
            #             try:
            #                 chunk = bytes.fromhex(raw.strip())
            #             except Exception as ex:
            #                 print("❌ Audio decode error:", ex)
            #         if chunk:
            #             self.audio_out.write(chunk)

            # ——————————————————————————————
            # 4) Everything else
            else:
                # e.g. transcription deltas, pings…
                continue
            
        
    def _feed_json_delta(self, delta: str):
        # accumulate
        self._json_buffer += delta

        # only attempt to parse once braces balance
        if self._json_buffer.count("{") == self._json_buffer.count("}"):
            try:
                obj = json.loads(self._json_buffer)
            except json.JSONDecodeError:
                print("Still malformed:", self._json_buffer)
            else:
                print("✅ Complete JSON:", obj)
                self.publish_payload(obj)
            finally:
                # reset for the next message
                self._json_buffer = ""
    def close(self):
        if hasattr(self, '_ws'):
            asyncio.create_task(self._ws.close())
