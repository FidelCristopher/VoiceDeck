import queue
import threading
from typing import Optional, List, Dict, Any
import numpy as np
import sounddevice as sd


class AudioCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 4000,
        device_index: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device_index = device_index

        self.audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=100)
        self.stream: Optional[sd.InputStream] = None
        self.is_running = False
        self.current_rms = 0.0
        self.on_level_callback = None

    @staticmethod
    def list_input_devices() -> List[Dict[str, Any]]:
        """List all available microphone input devices."""
        devices = sd.query_devices()
        input_devices = []
        for i, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                input_devices.append(
                    {
                        "index": i,
                        "name": dev.get("name"),
                        "hostapi": dev.get("hostapi"),
                        "channels": dev.get("max_input_channels"),
                        "default_sample_rate": dev.get("default_samplerate"),
                    }
                )
        return input_devices

    def _audio_callback(self, indata, frames, time_info, status):
        """Internal callback invoked by sounddevice for each chunk."""
        if status:
            pass  # Overflow or underflow can be safely handled

        # Convert to 16-bit PCM bytes for Vosk
        audio_int16 = (indata * 32767).astype(np.int16)
        raw_bytes = audio_int16.tobytes()

        # Compute RMS (Root Mean Square) for visual audio meter
        rms = float(np.sqrt(np.mean(indata**2)))
        self.current_rms = rms
        if self.on_level_callback:
            self.on_level_callback(rms)

        try:
            self.audio_queue.put_nowait(raw_bytes)
        except queue.Full:
            # Drop older chunks if queue is backlogged
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.put_nowait(raw_bytes)
            except (queue.Empty, queue.Full):
                pass

    def start(self):
        """Starts audio recording stream."""
        if self.is_running:
            return

        self.is_running = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.chunk_size,
            device=self.device_index,
            callback=self._audio_callback,
        )
        self.stream.start()

    def stop(self):
        """Stops audio recording stream."""
        self.is_running = False
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def read_chunk(self, timeout: float = 0.2) -> Optional[bytes]:
        """Reads one raw PCM chunk from the queue."""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
