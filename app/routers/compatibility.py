"""Mashup compatibility scoring router - compare two tracks for DJ mixing."""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models import CompatibilityResult, TrackInfo
from app.services.audio import analyze_audio_file

logger = logging.getLogger(__name__)
router = APIRouter()

# Camelot wheel for harmonic mixing compatibility
# Maps key names to Camelot codes
KEY_TO_CAMELOT = {
    "C major": "8B", "G major": "9B", "D major": "10B", "A major": "11B",
    "E major": "12B", "B major": "1B", "F# major": "2B", "C# major": "3B",
    "G# major": "4B", "D# major": "5B", "A# major": "6B", "F major": "7B",
    "A minor": "8A", "E minor": "9A", "B minor": "10A", "F# minor": "11A",
    "C# minor": "12A", "G# minor": "1A", "D# minor": "2A", "A# minor": "3A",
    "F minor": "4A", "C minor": "5A", "G minor": "6A", "D minor": "7A",
}

# Compatible Camelot transitions: same number (A<->B), +1, -1
def _camelot_number(code: str) -> int:
    return int(code[:-1])

def _camelot_letter(code: str) -> str:
    return code[-1]


def compute_key_compatibility(key_a: str, key_b: str) -> float:
    """Compute key compatibility score (0-100) using the Camelot wheel."""
    cam_a = KEY_TO_CAMELOT.get(key_a)
    cam_b = KEY_TO_CAMELOT.get(key_b)

    if not cam_a or not cam_b:
        return 50.0  # Unknown keys, neutral score

    if cam_a == cam_b:
        return 100.0  # Perfect match

    num_a, let_a = _camelot_number(cam_a), _camelot_letter(cam_a)
    num_b, let_b = _camelot_number(cam_b), _camelot_letter(cam_b)

    # Same number, different letter (major/minor switch) = great match
    if num_a == num_b and let_a != let_b:
        return 90.0

    # Adjacent numbers on the wheel (wrapping 12->1)
    diff = abs(num_a - num_b)
    if diff == 11:
        diff = 1  # Wrap around

    if let_a == let_b:
        if diff == 1:
            return 85.0  # Adjacent same mode
        elif diff == 2:
            return 60.0  # Two steps away
        elif diff <= 3:
            return 40.0

    # Cross-mode adjacent
    if diff <= 1:
        return 75.0
    elif diff == 2:
        return 50.0

    # Far apart
    return max(10.0, 100.0 - diff * 15.0)


def compute_bpm_compatibility(bpm_a: float, bpm_b: float) -> float:
    """Compute BPM compatibility score (0-100).

    Accounts for half-time / double-time relationships.
    """
    if bpm_a == 0 or bpm_b == 0:
        return 50.0

    # Check direct ratio and half/double time
    ratio = max(bpm_a, bpm_b) / min(bpm_a, bpm_b)

    # Perfect match
    if abs(bpm_a - bpm_b) < 1.0:
        return 100.0

    # Near match (within 3%)
    if ratio < 1.03:
        return 95.0

    # Double/half time match
    if abs(ratio - 2.0) < 0.05:
        return 85.0

    # Gradual falloff
    pct_diff = abs(bpm_a - bpm_b) / max(bpm_a, bpm_b) * 100
    if pct_diff <= 5:
        return 90.0
    elif pct_diff <= 10:
        return 70.0
    elif pct_diff <= 20:
        return 40.0
    else:
        return max(5.0, 100.0 - pct_diff * 3)


def compute_energy_compatibility(energy_a: float, energy_b: float) -> float:
    """Compute energy compatibility score (0-100)."""
    diff = abs(energy_a - energy_b)
    # Closer energy = more compatible for smooth mixing
    return round(max(0.0, 100.0 - diff * 200.0), 1)


def generate_recommendation(score: float, key_compat: float, bpm_compat: float) -> str:
    """Generate a human-readable mixing recommendation."""
    if score >= 85:
        return "Excellent match! These tracks should mix seamlessly."
    elif score >= 70:
        return "Good match. Minor pitch or tempo adjustments may help."
    elif score >= 50:
        return "Decent match. You'll need to pitch-shift or tempo-adjust for a smooth blend."
    elif score >= 30:
        return "Challenging mix. Significant key and/or BPM differences."
    else:
        return "Poor match. These tracks are unlikely to blend well without heavy editing."


@router.post("/compatibility", response_model=CompatibilityResult)
async def check_compatibility(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
):
    """Upload two audio files and get a mashup compatibility score.

    Compares key (using Camelot wheel), BPM, and energy levels.
    """
    for label, f in [("file_a", file_a), ("file_b", file_b)]:
        if not f.filename:
            raise HTTPException(status_code=400, detail=f"No filename provided for {label}")

    allowed_extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
    for label, f in [("file_a", file_a), ("file_b", file_b)]:
        ext = "." + f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}' for {label}.",
            )

    try:
        bytes_a = await file_a.read()
        bytes_b = await file_b.read()

        for label, data in [("file_a", bytes_a), ("file_b", bytes_b)]:
            if len(data) == 0:
                raise HTTPException(status_code=400, detail=f"{label} is empty")
            if len(data) > 50 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"{label} is too large (max 50MB)")

        # Analyze both tracks
        analysis_a = await analyze_audio_file(bytes_a, filename=file_a.filename)
        analysis_b = await analyze_audio_file(bytes_b, filename=file_b.filename)

        # Compute compatibility scores
        key_compat = compute_key_compatibility(analysis_a["key"], analysis_b["key"])
        bpm_compat = compute_bpm_compatibility(analysis_a["bpm"], analysis_b["bpm"])
        energy_compat = compute_energy_compatibility(analysis_a["energy"], analysis_b["energy"])

        # Weighted overall score: key matters most for DJs, then BPM, then energy
        overall = round(key_compat * 0.45 + bpm_compat * 0.40 + energy_compat * 0.15, 1)
        recommendation = generate_recommendation(overall, key_compat, bpm_compat)

        return CompatibilityResult(
            score=overall,
            key_compatibility=round(key_compat, 1),
            bpm_compatibility=round(bpm_compat, 1),
            energy_compatibility=round(energy_compat, 1),
            recommendation=recommendation,
            track_a=TrackInfo(**analysis_a),
            track_b=TrackInfo(**analysis_b),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compatibility check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Compatibility check failed: {str(e)}")
