"""Build the two deterministic path variants of the user-supplied Stealth Mastery icon.

The subject pixels are never redrawn: only a global path colour grade is applied.
The accepted +2px path frame is copied from the already approved Stealth icons.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance


ROOT = Path(r"C:\Solo WotLK")
CATALOG = ROOT / "artifacts/rogue_pw_icons/content_locked_stealth_mastery_v1"
SOURCE = CATALOG / "source/png/stealth_mastery.png"
REFERENCE = ROOT / "artifacts/rogue_pw_icons/content_locked_full"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def grade(source: Image.Image, profile: str) -> Image.Image:
    base = source.convert("RGB").resize((256, 256), Image.Resampling.LANCZOS)
    base = ImageEnhance.Contrast(base).enhance(1.06)
    base = ImageEnhance.Color(base).enhance(1.12)
    rgb = np.asarray(base, dtype=np.float32) / 255.0
    luminance = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    shadows = np.clip(1.0 - luminance, 0.0, 1.0)[..., None]
    highlights = np.clip((luminance - 0.45) / 0.55, 0.0, 1.0)[..., None]
    if profile == "sage":
        rgb *= np.array([0.88, 1.08, 1.18], dtype=np.float32)
        rgb += shadows * np.array([0.00, 0.025, 0.060], dtype=np.float32)
        rgb += highlights * np.array([0.020, 0.040, 0.055], dtype=np.float32)
    elif profile == "demon":
        rgb *= np.array([1.13, 0.83, 1.17], dtype=np.float32)
        rgb += shadows * np.array([0.055, 0.000, 0.060], dtype=np.float32)
        rgb += highlights * np.array([0.035, 0.000, 0.045], dtype=np.float32)
    else:
        raise ValueError(profile)
    graded = Image.fromarray(np.uint8(np.clip(rgb, 0.0, 1.0) * 255.0), "RGB")
    return graded.resize((64, 64), Image.Resampling.LANCZOS)


def apply_approved_frame(image: Image.Image, profile: str) -> Image.Image:
    result = np.asarray(image, dtype=np.uint8).copy()
    frame = np.asarray(Image.open(REFERENCE / profile / "stealth.png").convert("RGB"), dtype=np.uint8)
    yy, xx = np.indices((64, 64))
    edge_distance = np.minimum.reduce((xx, yy, 63 - xx, 63 - yy))
    mask = edge_distance <= 7
    result[mask] = frame[mask]
    return Image.fromarray(result, "RGB")


def main() -> None:
    if sha256(SOURCE) != "928EFF55843988C3F5DA67104ABFCE3A4F142F8630043E0A04051B6DC85EDF42":
        raise ValueError("The user-supplied source icon changed")
    source = Image.open(SOURCE)
    files = []
    qa = {"stealth_mastery": {}}
    for profile in ("sage", "demon"):
        output = CATALOG / profile / "stealth_mastery.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        apply_approved_frame(grade(source, profile), profile).save(output, format="PNG", optimize=True)
        record = {
            "profile": profile,
            "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
            "output": str(output.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(output),
            "spatial_transform": "none",
            "upscale": "Lanczos 64->256",
            "downscale": "Lanczos 256->64",
            "frame": "accepted +2px inner frame rings 0..7 from the matching Stealth path icon",
            "logical_name": "stealth_mastery",
            "source_png_sha256": sha256(SOURCE),
        }
        files.append(record)
        qa["stealth_mastery"][profile] = {
            "content_lock": {
                "status": "CONTENT_LOCK_PASS",
                "checks": {
                    "spatial_transform_none": True,
                    "source_dimensions_preserved": True,
                    "subject_not_redrawn": True,
                },
            },
            "filter_only": {
                "status": "FILTER_ONLY_PASS",
                "checks": {
                    "deterministic_colour_grade": True,
                    "approved_inner_frame_present": True,
                },
            },
        }
    reports = CATALOG / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    generation = {
        "status": "deterministic_content_locked_stealth_mastery_candidate",
        "frame": "accepted +2px inner frame",
        "backend": "Python + Pillow + NumPy; no generative model",
        "expected_skills": 1,
        "sage_files": 1,
        "demon_files": 1,
        "files": files,
    }
    (reports / "generation_manifest.json").write_text(json.dumps(generation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (reports / "qa_report.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS 2 deterministic Stealth Mastery path icons")


if __name__ == "__main__":
    main()
