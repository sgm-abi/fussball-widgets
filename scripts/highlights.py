import subprocess
import random
import os
import sys
import tempfile
import shutil
import yaml
from pathlib import Path


INSTAGRAM_FORMATS = {
    "reels":  (1080, 1920),  # 9:16
    "feed":   (1080, 1350),  # 4:5
    "square": (1080, 1080),  # 1:1
    "source": None,
}


def load_config(path: str = "scripts/highlights_config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_video(config: dict) -> str:
    """Lokale Datei verwenden oder von YouTube herunterladen."""
    url = config["source"].get("url", "").strip()
    local = config["source"].get("path", "video.mp4")

    if url:
        print(f"Lade herunter: {url}")
        subprocess.run(
            [
                "yt-dlp",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
                "-o", local,
                "--no-playlist",
                url,
            ],
            check=True,
        )

    if not Path(local).exists():
        raise FileNotFoundError(f"Video nicht gefunden: {local}")

    print(f"Video: {local}")
    return local


def cut_and_encode_clip(video: str, start: str, end: str, output: str, dimensions: tuple = None):
    """Clip frame-genau schneiden und re-encodieren (verhindert Keyframe-Freeze).

    dimensions: (w, h) für Instagram-Format, None = Originalformat beibehalten.
    """
    vf = ""
    if dimensions:
        w, h = dimensions
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"

    cmd = [
        "ffmpeg", "-y",
        "-ss", start,
        "-to", end,
        "-i", video,
    ]
    if vf:
        cmd += ["-vf", vf]
    cmd += [
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        output,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


TRANSITIONS = [
    "fade", "fadeblack", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "circleopen", "circleclose", "radial",
    "dissolve", "pixelize", "zoomin",
]


def concat_with_crossfade(clip_paths: list, durations: list, output: str, crossfade_sec: float, transition: str = "fade"):
    """Clips mit xfade zusammenfügen (max 10 pro Durchgang)."""
    BATCH = 10
    if len(clip_paths) == 1:
        shutil.copy(clip_paths[0], output)
        return

    tmpdir = tempfile.mkdtemp()
    try:
        if crossfade_sec <= 0 or len(clip_paths) > BATCH:
            # Einfacher Concat (oder zu viele Clips für xfade)
            list_path = os.path.join(tmpdir, "clips.txt")
            with open(list_path, "w") as f:
                for p in clip_paths:
                    f.write(f"file '{p}'\n")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", list_path, "-c", "copy", output],
                check=True, capture_output=True,
            )
            return

        inputs = []
        for p in clip_paths:
            inputs += ["-i", p]

        n = len(clip_paths)
        offsets = []
        cumulative = 0.0
        for i in range(n - 1):
            cumulative += durations[i] - crossfade_sec
            offsets.append(cumulative)

        def pick(t): return random.choice(TRANSITIONS) if t == "random" else t

        v_parts = [f"[0:v][1:v]xfade=transition={pick(transition)}:duration={crossfade_sec}:offset={offsets[0]:.3f}[v1]"]
        a_parts = [f"[0:a][1:a]acrossfade=d={crossfade_sec}[a1]"]

        for i in range(2, n):
            cv = "vout" if i == n - 1 else f"v{i}"
            ca = "aout" if i == n - 1 else f"a{i}"
            v_parts.append(f"[v{i-1}][{i}:v]xfade=transition={pick(transition)}:duration={crossfade_sec}:offset={offsets[i-1]:.3f}[{cv}]")
            a_parts.append(f"[a{i-1}][{i}:a]acrossfade=d={crossfade_sec}[{ca}]")

        if n == 2:
            v_parts[0] = v_parts[0].replace("[v1]", "[vout]")
            a_parts[0] = a_parts[0].replace("[a1]", "[aout]")

        subprocess.run(
            [
                "ffmpeg", "-y", *inputs,
                "-filter_complex", "; ".join(v_parts + a_parts),
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                output,
            ],
            check=True, capture_output=True,
        )
    finally:
        shutil.rmtree(tmpdir)


def main(config_path: str = "scripts/highlights_config.yaml"):
    config = load_config(config_path)
    video = get_video(config)

    out_cfg = config["output"]
    crossfade_sec = out_cfg.get("crossfade_sec", 0.5)
    transition = out_cfg.get("transition", "fade")
    fmt = out_cfg.get("instagram_format", "source")
    dimensions = INSTAGRAM_FORMATS.get(fmt)
    output_path = out_cfg.get("path", "highlights.mp4")

    clips = config["highlights"]
    print(f"Schneide {len(clips)} Clips ({fmt})...")

    with tempfile.TemporaryDirectory() as tmpdir:
        enc_clips = []
        durations = []

        for i, clip in enumerate(clips):
            label = clip.get("label", f"Clip {i+1}")
            print(f"  [{i+1}/{len(clips)}] {label}: {clip['start']} → {clip['end']}")

            enc = os.path.join(tmpdir, f"enc_{i:03d}.mp4")
            cut_and_encode_clip(video, clip["start"], clip["end"], enc, dimensions)

            # Dauer berechnen
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", enc],
                capture_output=True, text=True, check=True,
            )
            durations.append(float(probe.stdout.strip()))
            enc_clips.append(enc)

        print(f"Zusammenfügen mit {'Crossfade' if crossfade_sec > 0 else 'hartem Schnitt'}...")
        concat_with_crossfade(enc_clips, durations, output_path, crossfade_sec, transition)

    print(f"Fertig: {output_path}")


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "scripts/highlights_config.yaml"
    main(cfg)
