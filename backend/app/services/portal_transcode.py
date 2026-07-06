"""FFmpeg/ffprobe alapú videó-feldolgozás a Média Portálhoz - a Hype-repo-main
(különálló client-portál projekt) transcode.py 1:1 portolt logikája."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from math import gcd

from app.services import portal_storage as storage


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def probe(path: str) -> dict:
    """Return duration, width, height via ffprobe."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    stream = (data.get("streams") or [{}])[0]
    duration = float(data.get("format", {}).get("duration", 0) or 0)
    return {
        "width": int(stream.get("width", 0) or 0),
        "height": int(stream.get("height", 0) or 0),
        "duration": int(round(duration)),
    }


def resolution_label(height: int) -> str:
    if height >= 2160:
        return "4K"
    if height >= 1440:
        return "2K"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    if height >= 480:
        return "480p"
    return f"{height}p" if height else "SD"


def aspect_ratio_label(width: int, height: int) -> str:
    if not width or not height:
        return ""
    ratio = width / height
    common = {
        16 / 9: "16:9",
        9 / 16: "9:16",
        1 / 1: "1:1",
        4 / 3: "4:3",
        3 / 4: "3:4",
        21 / 9: "21:9",
        4 / 5: "4:5",
    }
    for value, label in common.items():
        if abs(ratio - value) < 0.04:
            return label
    d = gcd(width, height)
    return f"{width // d}:{height // d}"


def make_thumbnail(src: str, out_jpg: str, at_second: float = 1.0) -> None:
    _run([
        "ffmpeg", "-y", "-ss", str(at_second), "-i", src,
        "-frames:v", "1", "-vf", "scale=1280:-2",
        "-q:v", "3", out_jpg,
    ])


def make_hls(src: str, out_dir: str) -> str:
    """Generate HLS. Returns master playlist filename."""
    os.makedirs(out_dir, exist_ok=True)
    master = os.path.join(out_dir, "master.m3u8")
    _run([
        "ffmpeg", "-y", "-i", src,
        "-c:v", "libx264", "-c:a", "aac",
        "-profile:v", "main", "-crf", "20", "-sc_threshold", "0",
        "-g", "48", "-keyint_min", "48",
        "-hls_time", "6", "-hls_playlist_type", "vod",
        "-hls_segment_filename", os.path.join(out_dir, "seg_%03d.ts"),
        master,
    ])
    return master


def quick_metadata_and_thumb(remote_url: str, key_prefix: str) -> dict:
    """GYORS lépés: az R2 URL-ről közvetlenül kiolvassa a metaadatot, és kinyeri
    az első frame-et borítónak. Nem tölti le a teljes fájlt."""
    meta = probe(remote_url)

    with tempfile.TemporaryDirectory() as tmp:
        thumb = os.path.join(tmp, "thumb.jpg")
        at = min(1.0, (meta["duration"] / 2) if meta["duration"] else 1.0)
        make_thumbnail(remote_url, thumb, at_second=at)
        thumb_url = storage.upload_file(thumb, f"{key_prefix}/thumbnail.jpg", "image/jpeg")

    return {
        "thumbnail_url": thumb_url,
        "duration_seconds": meta["duration"],
        "width": meta["width"],
        "height": meta["height"],
        "resolution_label": resolution_label(meta["height"]),
        "aspect_ratio_label": aspect_ratio_label(meta["width"], meta["height"]),
    }


def build_hls(src_path: str, key_prefix: str) -> str:
    """LASSÚ lépés: HLS generálás a letöltött fájlból, feltöltés R2-be.
    Visszaadja a master playlist URL-jét. Hiba esetén dob."""
    with tempfile.TemporaryDirectory() as tmp:
        hls_dir = os.path.join(tmp, "hls")
        make_hls(src_path, hls_dir)
        hls_url = ""
        for fname in os.listdir(hls_dir):
            fpath = os.path.join(hls_dir, fname)
            ctype = "application/vnd.apple.mpegurl" if fname.endswith(".m3u8") else "video/mp2t"
            url = storage.upload_file(fpath, f"{key_prefix}/hls/{fname}", ctype)
            if fname == "master.m3u8":
                hls_url = url
    return hls_url
