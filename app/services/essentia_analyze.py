"""Audio analysis service using essentia for key, BPM, energy, and danceability detection."""

import logging
import tempfile
import os
import asyncio
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Camelot wheel mapping: (key, scale) -> Camelot code
# key is the essentia key string, scale is "major" or "minor"
CAMELOT_WHEEL = {
    ("C", "major"): "8B",
    ("G", "major"): "9B",
    ("D", "major"): "10B",
    ("A", "major"): "11B",
    ("E", "major"): "12B",
    ("B", "major"): "1B",
    ("F#", "major"): "2B",
    ("Gb", "major"): "2B",
    ("C#", "major"): "3B",
    ("Db", "major"): "3B",
    ("G#", "major"): "4B",
    ("Ab", "major"): "4B",
    ("D#", "major"): "5B",
    ("Eb", "major"): "5B",
    ("A#", "major"): "6B",
    ("Bb", "major"): "6B",
    ("F", "major"): "7B",
    ("A", "minor"): "8A",
    ("E", "minor"): "9A",
    ("B", "minor"): "10A",
    ("F#", "minor"): "11A",
    ("Gb", "minor"): "11A",
    ("C#", "minor"): "12A",
    ("Db", "minor"): "12A",
    ("G#", "minor"): "1A",
    ("Ab", "minor"): "1A",
    ("D#", "minor"): "2A",
    ("Eb", "minor"): "2A",
    ("A#", "minor"): "3A",
    ("Bb", "minor"): "3A",
    ("F", "minor"): "4A",
    ("C", "minor"): "5A",
    ("G", "minor"): "6A",
    ("D", "minor"): "7A",
}

# Reverse mapping: Camelot code -> (key, scale) for display
CAMELOT_TO_KEY = {v: k for k, v in CAMELOT_WHEEL.items()}


def _get_camelot_code(key: str, scale: str) -> Optional[str]:
    """Convert an essentia key/scale pair to a Camelot wheel code."""
    return CAMELOT_WHEEL.get((key, scale))


def _analyze_sync(file_path: str) -> dict:
    """Synchronous essentia analysis. Run in a thread to avoid blocking."""
    import essentia
    import essentia.standard as es

    # Load audio as mono float32 at 44100 Hz (essentia default)
    audio = es.MonoLoader(filename=file_path, sampleRate=44100)()
    duration = len(audio) / 44100.0

    # Key detection
    key_extractor = es.KeyExtractor()
    key, scale, key_strength = key_extractor(audio)

    # BPM detection
    rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
    bpm, beats, beats_confidence, _, beats_intervals = rhythm_extractor(audio)

    # Energy (RMS-based, normalized to 0-1)
    energy_algo = es.Energy()
    # Compute energy on short frames and average
    frame_size = 2048
    hop_size = 1024
    frame_gen = es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size)
    energies = []
    for frame in frame_gen:
        energies.append(energy_algo(frame))

    if energies:
        mean_energy = float(np.mean(energies))
        # Normalize: typical frame energy for loud music is ~0.01-0.5
        # Map to 0-1 range with a practical ceiling
        max_expected = 0.3
        normalized_energy = min(1.0, mean_energy / max_expected)
    else:
        normalized_energy = 0.0

    # Danceability
    danceability_algo = es.Danceability()
    danceability_value, _ = danceability_algo(audio)

    # Build Camelot code
    camelot = _get_camelot_code(key, scale)
    key_display = f"{key} {scale}"

    return {
        "key": key_display,
        "camelot": camelot or "N/A",
        "key_strength": round(float(key_strength), 4),
        "bpm": round(float(bpm), 1),
        "energy": round(float(normalized_energy), 4),
        "danceability": round(float(danceability_value), 4),
        "duration": round(duration, 2),
    }


async def analyze_audio_file(file_bytes: bytes, filename: str = "unknown") -> dict:
    """Analyze an audio file using essentia and return key, BPM, energy, danceability, and duration.

    Args:
        file_bytes: Raw bytes of the audio file.
        filename: Original filename for logging.

    Returns:
        Dictionary with key, camelot, bpm, energy, danceability, duration, and filename.
    """
    logger.info(f"Analyzing audio file (essentia): {filename} ({len(file_bytes)} bytes)")

    suffix = os.path.splitext(filename)[1] if "." in filename else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        result = await asyncio.to_thread(_analyze_sync, tmp_path)
        result["filename"] = filename
        logger.info(f"Essentia analysis complete for {filename}: {result}")
        return result
    finally:
        os.unlink(tmp_path)
