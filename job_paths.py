import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_VIDEO_DATASET_ROOT = (
    "/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset"
)

JOB_ID_WIDTH = 6


def normalize_cross_platform_path(raw_path: str | os.PathLike[str] | None) -> Path | None:
    if raw_path is None:
        return None

    text = str(raw_path).strip()
    if not text:
        return None

    wsl_match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", text)
    if os.name == "nt" and wsl_match:
        drive = wsl_match.group(1).upper()
        tail = wsl_match.group(2).replace("/", "\\")
        return Path(f"{drive}:\\{tail}")

    windows_match = re.match(r"^([a-zA-Z]):[\\/](.*)$", text)
    if os.name != "nt" and windows_match:
        drive = windows_match.group(1).lower()
        tail = windows_match.group(2).replace("\\", "/")
        return Path(f"/mnt/{drive}/{tail}")

    return Path(text)


def path_to_posix_string(path: Path) -> str:
    return str(path).replace("\\", "/")


def pad_job_id(value: object) -> str:
    raw = str(value).strip()
    if not raw:
        raise ValueError("El brief no contiene un id utilizable.")
    if not raw.isdigit():
        return raw
    return raw.zfill(JOB_ID_WIDTH)


def pad_story_id(value: object) -> str:
    raw = str(value).strip()
    if not raw:
        raise ValueError("La historia no contiene un story_id utilizable.")
    return raw


def build_story_job_id(story_id: object, created_at: datetime | None = None) -> str:
    normalized_story_id = pad_story_id(story_id)
    timestamp = (created_at or datetime.now(timezone.utc)).strftime("%Y%m%d_%H%M%S")
    return f"{normalized_story_id}_{timestamp}"


def build_unique_story_job_id(story_id: object, jobs_root: Path) -> str:
    probe_time = datetime.now(timezone.utc)
    while True:
        candidate = build_story_job_id(story_id, created_at=probe_time)
        if not (jobs_root / candidate).exists():
            return candidate
        probe_time += timedelta(seconds=1)


@dataclass(frozen=True)
class RuntimePaths:
    base_dir: Path
    data_dir: Path
    data_file: Path
    index_file: Path
    wsl_dir: Path
    dataset_root: Path
    jobs_root: Path
    voices_root: Path
    voices_index_file: Path
    legacy_jobs_root: Path

    def to_dataset_relative(self, path: Path) -> str:
        try:
            return path.relative_to(self.dataset_root).as_posix()
        except ValueError:
            return path_to_posix_string(path)


@dataclass(frozen=True)
class JobPaths:
    runtime: RuntimePaths
    job_id: str
    job_dir: Path
    job_file: Path
    status: Path
    source_dir: Path
    brief: Path
    script: Path
    manifest: Path
    scene_prompt_pack: Path
    scene_prompt_pack_markdown: Path
    rendered_workflow: Path
    audio_dir: Path
    audio: Path
    subtitles_dir: Path
    subtitles: Path
    logs_dir: Path
    editorial_log: Path
    audio_log: Path
    subtitles_log: Path
    legacy_job_dir: Path
    legacy_voice_config: Path

    @property
    def legacy_brief_candidates(self) -> list[Path]:
        return [self.legacy_job_dir / "brief.json"]

    @property
    def legacy_script_candidates(self) -> list[Path]:
        return [self.legacy_job_dir / "script.json"]

    @property
    def legacy_manifest_candidates(self) -> list[Path]:
        return [self.legacy_job_dir / "visual_manifest.json"]

    @property
    def legacy_rendered_workflow_candidates(self) -> list[Path]:
        return [
            self.legacy_job_dir / "rendered_comfy_workflow.json",
            self.legacy_job_dir / "images" / "rendered_comfy_workflow.json",
        ]

    @property
    def legacy_audio_candidates(self) -> list[Path]:
        return [self.legacy_job_dir / "audio" / "narration.wav"]

    @property
    def legacy_subtitles_candidates(self) -> list[Path]:
        return [self.legacy_job_dir / "subtitles" / "narration.srt"]


def first_existing_path(primary: Path, legacy_candidates: Iterable[Path] | None = None) -> Path:
    if primary.exists():
        return primary

    for candidate in legacy_candidates or []:
        if candidate.exists():
            return candidate

    return primary


def build_runtime_paths(
    *,
    dataset_root: str | os.PathLike[str] | None = None,
    jobs_root: str | os.PathLike[str] | None = None,
) -> RuntimePaths:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"

    resolved_dataset_root = normalize_cross_platform_path(
        dataset_root
        or os.getenv("VIDEO_DATASET_ROOT")
        or DEFAULT_VIDEO_DATASET_ROOT
    )
    if resolved_dataset_root is None:
        raise ValueError("No se pudo resolver VIDEO_DATASET_ROOT.")

    resolved_jobs_root = normalize_cross_platform_path(
        jobs_root
        or os.getenv("VIDEO_JOBS_ROOT")
        or str(resolved_dataset_root / "jobs")
    )
    if resolved_jobs_root is None:
        raise ValueError("No se pudo resolver VIDEO_JOBS_ROOT.")

    voices_root = resolved_dataset_root / "voices"

    return RuntimePaths(
        base_dir=base_dir,
        data_dir=data_dir,
        data_file=data_dir / "ideas.csv",
        index_file=data_dir / "index.csv",
        wsl_dir=base_dir / "wsl",
        dataset_root=resolved_dataset_root,
        jobs_root=resolved_jobs_root,
        voices_root=voices_root,
        voices_index_file=voices_root / "voices_index.json",
        legacy_jobs_root=base_dir / "jobs",
    )


def build_job_paths(job_id: str, runtime: RuntimePaths) -> JobPaths:
    padded_job_id = pad_job_id(job_id)
    job_dir = runtime.jobs_root / padded_job_id

    return JobPaths(
        runtime=runtime,
        job_id=padded_job_id,
        job_dir=job_dir,
        job_file=job_dir / "job.json",
        status=job_dir / "status.json",
        source_dir=job_dir / "source",
        brief=job_dir / "source" / f"{padded_job_id}_brief.json",
        script=job_dir / "source" / f"{padded_job_id}_script.json",
        manifest=job_dir / "source" / f"{padded_job_id}_visual_manifest.json",
        scene_prompt_pack=job_dir / "source" / f"{padded_job_id}_scene_prompt_pack.json",
        scene_prompt_pack_markdown=job_dir / "source" / f"{padded_job_id}_scene_prompt_pack.md",
        rendered_workflow=job_dir / "source" / f"{padded_job_id}_rendered_comfy_workflow.json",
        audio_dir=job_dir / "audio",
        audio=job_dir / "audio" / f"{padded_job_id}_narration.wav",
        subtitles_dir=job_dir / "subtitles",
        subtitles=job_dir / "subtitles" / f"{padded_job_id}_narration.srt",
        logs_dir=job_dir / "logs",
        editorial_log=job_dir / "logs" / f"{padded_job_id}_phase_editorial.log",
        audio_log=job_dir / "logs" / f"{padded_job_id}_phase_audio.log",
        subtitles_log=job_dir / "logs" / f"{padded_job_id}_phase_subtitles.log",
        legacy_job_dir=runtime.legacy_jobs_root / padded_job_id,
        legacy_voice_config=(runtime.legacy_jobs_root / padded_job_id / "voice.json"),
    )


def ensure_job_structure(job_paths: JobPaths) -> JobPaths:
    job_paths.source_dir.mkdir(parents=True, exist_ok=True)
    job_paths.audio_dir.mkdir(parents=True, exist_ok=True)
    job_paths.subtitles_dir.mkdir(parents=True, exist_ok=True)
    job_paths.logs_dir.mkdir(parents=True, exist_ok=True)
    return job_paths
