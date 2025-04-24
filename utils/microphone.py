import sounddevice as sd
import numpy as np
import wave
import os

class Microphone:
    def __init__(self, samplerate=16000, channels=1, dtype='int16', chunk_duration=0.25):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self.chunk_duration = chunk_duration
        self.chunk_size = int(self.samplerate * self.chunk_duration)

    def record(self, filename="recording.wav", duration=5):
        """
        Record audio for a fixed duration and save to a WAV file.
        
        """
        print(f"🎙️ Recording {duration} seconds to '{filename}'...")
        audio = sd.rec(int(duration * self.samplerate),
                       samplerate=self.samplerate,
                       channels=self.channels,
                       dtype=self.dtype)
        sd.wait()
        print("✅ Done recording!")

        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 2 bytes for int16
            wf.setframerate(self.samplerate)
            wf.writeframes(audio.tobytes())

        print(f"💾 Saved to {os.path.abspath(filename)}")

    def stream(self, callback):
        """
        Continuously reads audio chunks and passes them to a callback function.
        Useful for live streaming to WebSockets.
        Initializes microphone stream.
        :param samplerate: Sampling rate in Hz (OpenAI expects 16000)
        :param channels: 1 for mono
        :param dtype: int16 for PCM16
        :param chunk_duration: Time in seconds per chunk
        """
        def _process(indata, frames, time, status):
            if status:
                print(f"⚠️ {status}")
            audio_bytes = indata.astype(np.int16).tobytes()
            callback(audio_bytes)

        print("🎧 Live mic streaming started (Ctrl+C to stop)...")
        try:
            with sd.InputStream(samplerate=self.samplerate,
                                channels=self.channels,
                                dtype=self.dtype,
                                blocksize=self.chunk_size,
                                callback=_process):
                while True:
                    sd.sleep(int(self.chunk_duration * 1000))
        except KeyboardInterrupt:
            print("🛑 Stopped streaming.")



