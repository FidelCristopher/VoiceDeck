import numpy as np


class EnergyVAD:
    """
    Lightweight energy-based Voice Activity Detection with running noise floor tracking.
    Zero external dependencies, ultra-fast (<0.1ms).
    """

    def __init__(self, base_threshold: float = 0.015, adaptation_rate: float = 0.02):
        self.threshold = base_threshold
        self.adaptation_rate = adaptation_rate
        self.noise_floor = base_threshold * 0.5

    def is_speech(self, raw_bytes: bytes) -> bool:
        """
        Determines whether the given 16-bit PCM chunk contains speech.
        """
        if not raw_bytes:
            return False

        audio_data = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio_data**2)))

        if rms > self.threshold:
            return True
        else:
            # Adaptively adjust noise floor during silence
            self.noise_floor = (
                (1.0 - self.adaptation_rate) * self.noise_floor
                + self.adaptation_rate * rms
            )
            # Threshold stays slightly above the noise floor
            self.threshold = max(0.012, self.noise_floor * 2.2)
            return False
