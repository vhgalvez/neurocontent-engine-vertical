#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from config import configure_runtime, get_runtime_paths  # noqa: E402
from director import update_status  # noqa: E402
from job_paths import build_job_paths, ensure_job_structure, iter_job_ids as iter_runtime_job_ids  # noqa: E402

WHISPERX_PYTHON = os.getenv("WHISPERX_PYTHON", "/home/victory/miniconda3/bin/python")
WHISPER_MODEL = os.getenv("WHISPERX_MODEL", "small")
LANGUAGE = os.getenv("WHISPERX_LANGUAGE", "es")
DEVICE = os.getenv("WHISPERX_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "int8")
NO_ALIGN = os.getenv("WHISPERX_NO_ALIGN", "true").lower() == "true"
FALLBACK_DEVICE = os.getenv("WHISPERX_FALLBACK_DEVICE", "cpu")
FALLBACK_COMPUTE_TYPE = os.getenv("WHISPERX_FALLBACK_COMPUTE_TYPE", "int8")
OVERWRITE = os.getenv("WHISPERX_OVERWRITE", "false").lower() == "true"
STRICT = os.getenv("WHISPERX_STRICT", "false").lower() == "true"
PREFLIGHT = os.getenv("WHISPERX_PREFLIGHT", "true").lower() == "true"
LOG_TAIL_CHARS = int(os.getenv("WHISPERX_LOG_TAIL_CHARS", "6000"))
TIMEOUT_SECONDS = int(os.getenv("WHISPERX_TIMEOUT_SECONDS", "0"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera subtitulos SRT por job.")
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument("--job-id", action="append", dest="job_ids", help="Procesa un job especifico. Repetible.")
    return parser.parse_args()


def iter_job_ids(job_ids: list[str] | None) -> list[str]:
    runtime = get_runtime_paths()
    if job_ids:
        return job_ids
    return iter_runtime_job_ids(runtime)


def build_cmd(python_bin: str, wav_path: Path, output_dir: Path, device: str, compute_type: str, no_align: bool) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "whisperx",
        str(wav_path),
        "--model",
        WHISPER_MODEL,
        "--language",
        LANGUAGE,
        "--device",
        device,
        "--compute_type",
        compute_type,
        "--output_format",
        "srt",
        "--output_dir",
        str(output_dir),
    ]
    if no_align:
        cmd.append("--no_align")
    return cmd


def short_output(text: str, max_chars: int = LOG_TAIL_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def run_cmd(cmd: list[str], log_path: Path | None = None) -> tuple[bool, int, str]:
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=None if TIMEOUT_SECONDS <= 0 else TIMEOUT_SECONDS,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        if log_path:
            log_path.write_text(output, encoding="utf-8")
        return True, result.returncode, output
    except subprocess.TimeoutExpired as exc:
        output = f"TIMEOUT after {TIMEOUT_SECONDS}s\n{(exc.stdout or '')}\n{(exc.stderr or '')}"
        if log_path:
            log_path.write_text(output, encoding="utf-8")
        return False, 124, output
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        if log_path:
            log_path.write_text(output, encoding="utf-8")
        return False, exc.returncode, output


def preflight_runtime(python_path: Path) -> None:
    print("Preflight: comprobando entorno WhisperX...")
    ok, code, output = run_cmd([str(python_path), "-m", "whisperx", "--help"])
    if not ok:
        raise RuntimeError(f"Falló el preflight de whisperx CLI.\nExit code: {code}\n{short_output(output)}")
    print("Preflight OK")


def normalize_generated_srt(output_dir: Path, wav_path: Path, target_srt_path: Path) -> bool:
    generated_name = output_dir / f"{wav_path.stem}.srt"
    if target_srt_path.exists():
        return True
    if generated_name.exists() and generated_name != target_srt_path:
        generated_name.replace(target_srt_path)
        return True
    return target_srt_path.exists()


def process_job(job_id: str, python_path: Path) -> bool:
    job_paths = ensure_job_structure(build_job_paths(job_id, get_runtime_paths()))
    wav_path = job_paths.audio if job_paths.audio.exists() else job_paths.legacy_audio_candidates[0]
    srt_path = job_paths.subtitles
    main_log = job_paths.subtitles_log
    fallback_log = job_paths.logs_dir / f"{job_paths.job_id}_phase_subtitles_fallback.log"

    if not wav_path.exists():
        print(f"[{job_id}] narration.wav no existe, se omite")
        update_status(job_paths.status, subtitles_generated=False, last_step="subs_missing_audio")
        return False
    if srt_path.exists() and not OVERWRITE:
        print(f"[{job_id}] narration.srt ya existe, se omite")
        update_status(job_paths.status, subtitles_generated=True, last_step="subs_skipped")
        return True

    main_cmd = build_cmd(str(python_path), wav_path, srt_path.parent, DEVICE, COMPUTE_TYPE, NO_ALIGN)
    ok, code, output = run_cmd(main_cmd, log_path=main_log)
    if ok:
        exists = normalize_generated_srt(srt_path.parent, wav_path, srt_path)
        update_status(job_paths.status, subtitles_generated=exists, last_step="subtitles_generated")
        return exists

    print(f"[{job_id}] Falló principal (exit={code}). {short_output(output)}")
    fallback_cmd = build_cmd(str(python_path), wav_path, srt_path.parent, FALLBACK_DEVICE, FALLBACK_COMPUTE_TYPE, True)
    ok, code, output = run_cmd(fallback_cmd, log_path=fallback_log)
    if ok:
        exists = normalize_generated_srt(srt_path.parent, wav_path, srt_path)
        update_status(job_paths.status, subtitles_generated=exists, last_step="subtitles_generated_fallback")
        return exists

    print(f"[{job_id}] Falló fallback (exit={code}). {short_output(output)}")
    update_status(job_paths.status, subtitles_generated=False, last_step="subtitles_error")
    if STRICT:
        raise RuntimeError(f"[{job_id}] WhisperX falló en principal y fallback")
    return False


def main() -> int:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)

    python_path = Path(WHISPERX_PYTHON)
    if not python_path.exists():
        raise FileNotFoundError(f"No existe WHISPERX_PYTHON: {WHISPERX_PYTHON}")
    if PREFLIGHT:
        preflight_runtime(python_path)

    job_ids = iter_job_ids(args.job_ids)
    if not job_ids:
        print("No hay jobs para procesar.")
        return 0

    ok_count = 0
    error_count = 0
    for job_id in job_ids:
        try:
            if process_job(job_id, python_path):
                ok_count += 1
            else:
                error_count += 1
        except Exception as exc:
            error_count += 1
            print(f"[{job_id}] ERROR no controlado: {exc}")
            job_paths = ensure_job_structure(build_job_paths(job_id, get_runtime_paths()))
            update_status(job_paths.status, subtitles_generated=False, last_step="subtitles_exception")
            if STRICT:
                raise

    print(f"Subtítulos completados (ok={ok_count}, errores={error_count})")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
