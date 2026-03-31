"""Modal serverless function for track identification.

Runs Chromaprint fingerprinting on Modal's infrastructure, useful
when the main server doesn't have fpcalc installed.

Deploy with: modal deploy modal_functions/trackid.py
"""

import modal

app = modal.App("orryy-trackid")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libchromaprint-tools", "ffmpeg")
    .pip_install(
        "pyacoustid==1.3.0",
        "httpx==0.28.1",
    )
)


@app.function(image=image, timeout=120)
def identify_track_remote(
    audio_url: str,
    acoustid_api_key: str,
) -> dict:
    """Identify a track from a URL using AcoustID.

    Args:
        audio_url: URL to download the audio file.
        acoustid_api_key: AcoustID API key.

    Returns:
        Dict with identification results.
    """
    import tempfile
    import os
    import acoustid
    import httpx

    # Download the audio file
    with httpx.Client(timeout=120.0) as client:
        resp = client.get(audio_url)
        resp.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.write(resp.content)
    tmp.close()

    try:
        duration, fingerprint = acoustid.fingerprint_file(tmp.name)

        # Look up against AcoustID
        with httpx.Client(timeout=30.0) as client:
            lookup_resp = client.post(
                "https://api.acoustid.org/v2/lookup",
                data={
                    "client": acoustid_api_key,
                    "duration": str(int(duration)),
                    "fingerprint": fingerprint,
                    "meta": "recordings releasegroups",
                },
            )
            lookup_resp.raise_for_status()
            data = lookup_resp.json()

        results = data.get("results", [])
        if not results:
            return {
                "identified": False,
                "title": None,
                "artist": None,
                "album": None,
                "release_date": None,
                "score": None,
                "acoustid": None,
                "recordings": [],
            }

        best = results[0]
        score = best.get("score", 0)
        acoustid_id = best.get("id")
        recordings = best.get("recordings", [])

        title = None
        artist = None
        album = None
        release_date = None

        if recordings:
            rec = recordings[0]
            title = rec.get("title")
            artists = rec.get("artists", [])
            if artists:
                artist = artists[0].get("name")
            release_groups = rec.get("releasegroups", [])
            if release_groups:
                rg = release_groups[0]
                album = rg.get("title")
                release_date = rg.get("firstreleasedate")

        return {
            "identified": True,
            "title": title,
            "artist": artist,
            "album": album,
            "release_date": release_date,
            "score": round(score, 4),
            "acoustid": acoustid_id,
            "recordings": recordings[:5],
        }

    finally:
        os.unlink(tmp.name)
