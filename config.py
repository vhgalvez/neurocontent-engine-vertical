import os

from job_paths import JOB_ID_WIDTH, build_runtime_paths

DEFAULT_TEXT_MODEL = "qwen3:8b"
TEXT_MODEL_ENV_VAR = "TEXT_MODEL"
TARGET_AUDIO_MINUTES_ENV_VAR = "TARGET_AUDIO_MINUTES"

BASE_DIR = None
DATA_DIR = None
DATASET_ROOT = None
DATASET_NAME = None
STORIES_DIR = None
STORIES_DRAFT_DIR = None
STORIES_PRODUCTION_DIR = None
STORIES_ARCHIVE_DIR = None
JOBS_DIR = None
OUTPUTS_DIR = None
LOGS_DIR = None
STATE_DIR = None
VOICES_DIR = None
VOICES_INDEX_FILE = None
WSL_DIR = None
DATA_FILE = None
INDEX_FILE = None
_RUNTIME_PATHS = None
TEXT_MODEL = None
TARGET_AUDIO_MINUTES = None


def _refresh_runtime_globals() -> None:
    global BASE_DIR
    global DATA_DIR
    global DATASET_ROOT
    global DATASET_NAME
    global STORIES_DIR
    global STORIES_DRAFT_DIR
    global STORIES_PRODUCTION_DIR
    global STORIES_ARCHIVE_DIR
    global JOBS_DIR
    global OUTPUTS_DIR
    global LOGS_DIR
    global STATE_DIR
    global VOICES_DIR
    global VOICES_INDEX_FILE
    global WSL_DIR
    global DATA_FILE
    global INDEX_FILE

    runtime = get_runtime_paths()
    BASE_DIR = runtime.base_dir
    DATA_DIR = runtime.data_dir
    DATASET_ROOT = runtime.dataset_root
    DATASET_NAME = runtime.dataset_name
    STORIES_DIR = runtime.stories_root
    STORIES_DRAFT_DIR = runtime.stories_draft_dir
    STORIES_PRODUCTION_DIR = runtime.stories_production_dir
    STORIES_ARCHIVE_DIR = runtime.stories_archive_dir
    JOBS_DIR = runtime.jobs_root
    OUTPUTS_DIR = runtime.outputs_root
    LOGS_DIR = runtime.logs_root
    STATE_DIR = runtime.state_root
    VOICES_DIR = runtime.voices_root
    VOICES_INDEX_FILE = runtime.voices_index_file
    WSL_DIR = runtime.wsl_dir
    DATA_FILE = runtime.data_file
    INDEX_FILE = runtime.index_file


def configure_runtime(
    *,
    dataset_root: str | os.PathLike[str] | None = None,
    jobs_root: str | os.PathLike[str] | None = None,
    text_model: str | None = None,
    target_audio_minutes: float | None = None,
):
    global _RUNTIME_PATHS
    _RUNTIME_PATHS = build_runtime_paths(
        dataset_root=dataset_root,
        jobs_root=jobs_root,
    )
    _refresh_runtime_globals()
    set_text_model(text_model)
    set_target_audio_minutes(target_audio_minutes)
    return _RUNTIME_PATHS


def get_runtime_paths():
    global _RUNTIME_PATHS
    if _RUNTIME_PATHS is None:
        _RUNTIME_PATHS = build_runtime_paths()
        _refresh_runtime_globals()
    return _RUNTIME_PATHS


get_runtime_paths()

OLLAMA_URL = "http://localhost:11434/api/chat"


def resolve_text_model(candidate: str | None = None) -> str:
    explicit = str(candidate or "").strip()
    if explicit:
        return explicit

    env_value = os.getenv(TEXT_MODEL_ENV_VAR, "").strip()
    if env_value:
        return env_value

    return DEFAULT_TEXT_MODEL


def set_text_model(candidate: str | None = None) -> str:
    global TEXT_MODEL
    TEXT_MODEL = resolve_text_model(candidate)
    return TEXT_MODEL


def get_text_model() -> str:
    global TEXT_MODEL
    if TEXT_MODEL is None:
        TEXT_MODEL = resolve_text_model()
    return TEXT_MODEL


set_text_model()


def _normalize_target_audio_minutes(candidate: float | str | None) -> float | None:
    if candidate is None:
        return None

    raw = str(candidate).strip()
    if not raw:
        return None

    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(
            f"TARGET_AUDIO_MINUTES invalido: {candidate}. Debe ser un numero positivo."
        ) from exc

    if value <= 0:
        raise ValueError(
            f"TARGET_AUDIO_MINUTES invalido: {candidate}. Debe ser mayor que cero."
        )

    return value


def resolve_target_audio_minutes(candidate: float | str | None = None) -> float | None:
    explicit = _normalize_target_audio_minutes(candidate)
    if explicit is not None:
        return explicit

    env_value = os.getenv(TARGET_AUDIO_MINUTES_ENV_VAR, "").strip()
    if env_value:
        return _normalize_target_audio_minutes(env_value)

    return None


def set_target_audio_minutes(candidate: float | str | None = None) -> float | None:
    global TARGET_AUDIO_MINUTES
    TARGET_AUDIO_MINUTES = resolve_target_audio_minutes(candidate)
    return TARGET_AUDIO_MINUTES


def get_target_audio_minutes() -> float | None:
    global TARGET_AUDIO_MINUTES
    if TARGET_AUDIO_MINUTES is None:
        TARGET_AUDIO_MINUTES = resolve_target_audio_minutes()
    return TARGET_AUDIO_MINUTES


set_target_audio_minutes()

OPTIONS = {
    "num_ctx": 4096,
    "num_predict": 900,
    "temperature": 0.82,
    "top_p": 0.92,
    "repeat_penalty": 1.08,
}

REQUEST_TIMEOUT_SECONDS = 180
OLLAMA_MAX_RETRIES = int(os.getenv("NC_OLLAMA_MAX_RETRIES", "3"))

OVERWRITE_ALL = os.getenv("NC_OVERWRITE_ALL", "false").lower() == "true"
OVERWRITE_SCRIPT = os.getenv("NC_OVERWRITE_SCRIPT", "false").lower() == "true" or OVERWRITE_ALL
OVERWRITE_MANIFEST = os.getenv("NC_OVERWRITE_MANIFEST", "false").lower() == "true" or OVERWRITE_ALL
