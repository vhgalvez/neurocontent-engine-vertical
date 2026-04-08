import os

from job_paths import JOB_ID_WIDTH, build_runtime_paths

DEFAULT_TEXT_MODEL = "qwen3:8b"
TEXT_MODEL_ENV_VAR = "TEXT_MODEL"

BASE_DIR = None
DATA_DIR = None
DATASET_ROOT = None
JOBS_DIR = None
VOICES_DIR = None
VOICES_INDEX_FILE = None
WSL_DIR = None
DATA_FILE = None
INDEX_FILE = None
_RUNTIME_PATHS = None
TEXT_MODEL = None


def _refresh_runtime_globals() -> None:
    global BASE_DIR
    global DATA_DIR
    global DATASET_ROOT
    global JOBS_DIR
    global VOICES_DIR
    global VOICES_INDEX_FILE
    global WSL_DIR
    global DATA_FILE
    global INDEX_FILE

    runtime = get_runtime_paths()
    BASE_DIR = runtime.base_dir
    DATA_DIR = runtime.data_dir
    DATASET_ROOT = runtime.dataset_root
    JOBS_DIR = runtime.jobs_root
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
):
    global _RUNTIME_PATHS
    _RUNTIME_PATHS = build_runtime_paths(
        dataset_root=dataset_root,
        jobs_root=jobs_root,
    )
    _refresh_runtime_globals()
    set_text_model(text_model)
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
