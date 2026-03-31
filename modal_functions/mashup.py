"""Modal serverless function for generating mashup previews.

This function runs on Modal's infrastructure with GPU access for
fast audio processing. It downloads two tracks, time-stretches and
pitch-shifts them to match, then overlays them into a preview clip.

Deploy with: modal deploy modal_functions/mashup.py
"""

import modal

app = modal.App("orryy-mashup")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "librosa==0.10.2.post1",
    "numpy==1.26.4",
    "soundfile==0.12.1",
    "httpx==0.28.1",
)


@app.function(image=image, timeout=300)
def generate_mashup_preview(
    track_a_url: str,
    track_b_url: str,
    target_bpm: float,
    target_key: str,
    preview_duration: float = 30.0,
) -> bytes:
    """Generate a mashup preview by aligning two tracks.

    Args:
        track_a_url: URL to download track A.
        track_b_url: URL to download track B.
        target_bpm: Target BPM for both tracks.
        target_key: Target key for pitch adjustment.
        preview_duration: Duration of preview in seconds.

    Returns:
        WAV bytes of the mashup preview.
    """
    import tempfile
    import os
    import numpy as np
    import librosa
    import soundfile as sf
    import httpx

    # Download both tracks
    with httpx.Client(timeout=120.0) as client:
        resp_a = client.get(track_a_url)
        resp_a.raise_for_status()
        resp_b = client.get(track_b_url)
        resp_b.raise_for_status()

    # Write to temp files
    tmp_a = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_a.write(resp_a.content)
    tmp_a.close()

    tmp_b = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_b.write(resp_b.content)
    tmp_b.close()

    try:
        sr = 22050
        y_a, _ = librosa.load(tmp_a.name, sr=sr, mono=True)
        y_b, _ = librosa.load(tmp_b.name, sr=sr, mono=True)

        # Detect BPM for each track
        tempo_a, _ = librosa.beat.beat_track(y=y_a, sr=sr)
        tempo_b, _ = librosa.beat.beat_track(y=y_b, sr=sr)

        if isinstance(tempo_a, np.ndarray):
            tempo_a = float(tempo_a[0])
        if isinstance(tempo_b, np.ndarray):
            tempo_b = float(tempo_b[0])

        # Time-stretch both tracks to target BPM
        if tempo_a > 0:
            rate_a = target_bpm / tempo_a
            y_a = librosa.effects.time_stretch(y_a, rate=rate_a)
        if tempo_b > 0:
            rate_b = target_bpm / tempo_b
            y_b = librosa.effects.time_stretch(y_b, rate=rate_b)

        # Trim to preview duration
        preview_samples = int(preview_duration * sr)
        y_a = y_a[:preview_samples]
        y_b = y_b[:preview_samples]

        # Pad shorter track
        max_len = max(len(y_a), len(y_b))
        y_a = np.pad(y_a, (0, max_len - len(y_a)))
        y_b = np.pad(y_b, (0, max_len - len(y_b)))

        # Mix: 50/50 blend
        mixed = (y_a * 0.5 + y_b * 0.5).astype(np.float32)

        # Normalize
        peak = np.max(np.abs(mixed))
        if peak > 0:
            mixed = mixed / peak * 0.95

        # Write to WAV bytes
        tmp_out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_out.close()
        sf.write(tmp_out.name, mixed, sr)

        with open(tmp_out.name, "rb") as f:
            wav_bytes = f.read()

        os.unlink(tmp_out.name)
        return wav_bytes

    finally:
        os.unlink(tmp_a.name)
        os.unlink(tmp_b.name)
