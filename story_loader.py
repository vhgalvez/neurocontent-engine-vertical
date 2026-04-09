from pathlib import Path
from typing import Any

FRONTMATTER_DELIM = "---"
VALID_STORY_STATES = {"draft", "pending", "processing", "done", "archived", "error"}
DATASET_STORY_BUCKETS = ("draft", "production", "archive")

REQUIRED_METADATA_FIELDS = (
    "id",
    "estado",
    "idioma",
    "plataforma",
    "formato",
    "duracion_seg",
    "objetivo",
    "tono",
    "ritmo",
    "estilo_narracion",
    "tipo_cierre",
)

REQUIRED_BODY_SECTIONS = (
    "title",
    "hook",
    "historia",
    "cta",
)

EDITORIAL_DEFAULTS = {
    "nicho": "",
    "subnicho": "",
    "avatar": "",
    "audiencia": "",
    "dolor_principal": "",
    "deseo_principal": "",
    "miedo_principal": "",
    "angulo": "",
    "tipo_hook": "",
    "tesis": "",
    "enemigo": "",
    "error_comun": "",
    "transformacion_prometida": "",
    "emocion_principal": "",
    "emocion_secundaria": "",
    "nivel_intensidad": "",
    "cta_tipo": "",
    "keywords": "",
    "referencias": "",
    "nivel_agresividad_copy": "",
    "objetivo_retencion": "",
}


def _normalize_value(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_section_name(raw_name: str) -> str:
    return raw_name.strip().lower().replace(" ", "_")


def _parse_frontmatter(lines: list[str], path_label: str) -> tuple[dict[str, str], int]:
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        raise ValueError(f"{path_label}: el archivo no comienza con frontmatter ---")

    end_idx = 1
    while end_idx < len(lines) and lines[end_idx].strip() != FRONTMATTER_DELIM:
        end_idx += 1
    if end_idx == len(lines):
        raise ValueError(f"{path_label}: no se encontro cierre de frontmatter ---")

    metadata: dict[str, str] = {}
    for index, line in enumerate(lines[1:end_idx], start=2):
        stripped = line.strip()
        if not stripped:
            continue
        if ":" not in line:
            raise ValueError(
                f"{path_label}: linea invalida en frontmatter ({index}): {line!r}"
            )
        key, value = line.split(":", 1)
        normalized_key = _normalize_section_name(key)
        if not normalized_key:
            raise ValueError(f"{path_label}: clave vacia en frontmatter ({index})")
        metadata[normalized_key] = value.strip()

    return metadata, end_idx


def _parse_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    for line in body.splitlines():
        if line.startswith("# "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = "title"
            buffer = [line[2:].strip()]
            continue

        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = _normalize_section_name(line[3:])
            buffer = []
            continue

        if current is not None:
            buffer.append(line)

    if current is not None:
        sections[current] = "\n".join(buffer).strip()

    return sections


def _validate_required_metadata(metadata: dict[str, str], path_label: str) -> None:
    missing = [field for field in REQUIRED_METADATA_FIELDS if not _normalize_value(metadata.get(field))]
    if missing:
        raise ValueError(
            f"{path_label}: frontmatter incompleto. Faltan campos obligatorios: {', '.join(missing)}"
        )


def _normalize_story_id(raw_id: Any, *, path_label: str) -> str:
    normalized_id = _normalize_value(raw_id)
    if not normalized_id:
        raise ValueError(f"{path_label}: el campo 'id' no puede estar vacio")
    return normalized_id


def _normalize_story_state(raw_state: Any, *, path_label: str) -> str:
    normalized_state = _normalize_value(raw_state).lower()
    if not normalized_state:
        raise ValueError(f"{path_label}: el campo 'estado' no puede estar vacio")
    if normalized_state not in VALID_STORY_STATES:
        allowed = ", ".join(sorted(VALID_STORY_STATES))
        raise ValueError(
            f"{path_label}: estado invalido '{normalized_state}'. Estados soportados: {allowed}"
        )
    return normalized_state


def validate_story_metadata(metadata: dict[str, str], story_path: str | Path) -> dict[str, str]:
    path = Path(story_path)
    path_label = str(path)

    _validate_required_metadata(metadata, path_label)

    validated = dict(metadata)
    validated["id"] = _normalize_story_id(validated.get("id"), path_label=path_label)
    validated["estado"] = _normalize_story_state(validated.get("estado"), path_label=path_label)

    file_stem = path.stem.strip()
    if file_stem and file_stem != validated["id"]:
        raise ValueError(
            f"{path_label}: el nombre del archivo no coincide con el id interno.\n"
            f"- nombre de archivo: {file_stem}.md\n"
            f"- id en frontmatter: {validated['id']}\n"
            "Sugerencia: renombra el archivo para que coincida con el id o corrige el campo 'id' del frontmatter."
        )

    return validated


def _validate_required_sections(sections: dict[str, str], path_label: str) -> None:
    missing = [section for section in REQUIRED_BODY_SECTIONS if not _normalize_value(sections.get(section))]
    if missing:
        pretty_missing = ", ".join(
            f"## {section.title()}" if section != "title" else "# Titulo"
            for section in missing
        )
        raise ValueError(
            f"{path_label}: faltan secciones obligatorias o estan vacias: {pretty_missing}"
        )


def _normalize_story_metadata(metadata: dict[str, str], sections: dict[str, str]) -> dict[str, str]:
    normalized = dict(EDITORIAL_DEFAULTS)
    normalized.update(metadata)

    normalized["render_targets"] = _normalize_value(
        metadata.get("render_targets") or metadata.get("render_target") or "vertical"
    )
    normalized["default_render_target"] = _normalize_value(
        metadata.get("default_render_target") or normalized["render_targets"].split("|")[0]
    )
    normalized["target_aspect_ratio"] = _normalize_value(
        metadata.get("target_aspect_ratio") or metadata.get("aspect_ratio") or "9:16"
    )
    normalized["content_orientation"] = _normalize_value(
        metadata.get("content_orientation")
        or (
            "multi"
            if "|" in normalized["render_targets"]
            else "landscape"
            if normalized["render_targets"] == "horizontal"
            else "portrait"
        )
    )

    normalized["idea_central"] = _normalize_value(
        metadata.get("idea_central") or sections.get("title")
    )
    normalized["historia_base"] = _normalize_value(
        metadata.get("historia_base") or sections.get("historia")
    )
    normalized["cta_texto"] = _normalize_value(
        metadata.get("cta_texto") or sections.get("cta")
    )
    normalized["notas_direccion"] = _normalize_value(
        metadata.get("notas_direccion") or sections.get("visual_notes")
    )
    normalized["prohibido"] = _normalize_value(
        sections.get("prohibido") or metadata.get("prohibido")
    )

    for key, value in list(normalized.items()):
        normalized[key] = _normalize_value(value)

    return normalized


def parse_story_markdown(content: str, *, path_label: str = "<memory>") -> dict[str, Any]:
    lines = content.splitlines()
    metadata, end_idx = _parse_frontmatter(lines, path_label)
    body = "\n".join(lines[end_idx + 1 :])
    sections = _parse_sections(body)

    _validate_required_sections(sections, path_label)
    normalized_metadata = _normalize_story_metadata(metadata, sections)

    story = {
        "metadata": normalized_metadata,
        "title": _normalize_value(sections.get("title")),
        "hook": _normalize_value(sections.get("hook")),
        "historia": _normalize_value(sections.get("historia")),
        "cta": _normalize_value(sections.get("cta")),
        "visual_notes": _normalize_value(sections.get("visual_notes")),
        "prohibido": _normalize_value(
            sections.get("prohibido") or normalized_metadata.get("prohibido")
        ),
    }

    if not story["historia"]:
        raise ValueError(f"{path_label}: la historia no puede estar vacia")

    return story


def load_story_markdown(path: str | Path) -> dict[str, Any]:
    story_path = Path(path)
    story = parse_story_markdown(
        story_path.read_text(encoding="utf-8"),
        path_label=str(story_path),
    )
    story["metadata"] = validate_story_metadata(story["metadata"], story_path)
    story["story_file"] = story_path.as_posix()
    return story


def _raise_duplicate_story_id_error(
    duplicate_id: str,
    current_file: Path,
    previous_file: Path,
) -> None:
    raise ValueError(
        "ID duplicado en historias Markdown dentro del dataset.\n"
        f"- id duplicado: {duplicate_id}\n"
        f"- archivo actual: {current_file}\n"
        f"- archivo anterior: {previous_file}\n"
        "Sugerencia: no reutilices story_id dentro del mismo dataset. "
        "Crea un id nuevo o elimina/renombra la historia conflictiva."
    )


def load_all_stories(directory: str | Path) -> list[dict[str, Any]]:
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"No existe el directorio de historias Markdown: {dir_path}")

    story_files = sorted(dir_path.glob("*.md"))
    if not story_files:
        raise FileNotFoundError(f"No se encontraron historias Markdown en: {dir_path}")

    stories: list[dict[str, Any]] = []
    seen_ids: dict[str, Path] = {}

    for story_file in story_files:
        story = load_story_markdown(story_file)
        source_id = story["metadata"]["id"]
        previous = seen_ids.get(source_id)
        if previous is not None:
            _raise_duplicate_story_id_error(source_id, story_file, previous)
        seen_ids[source_id] = story_file
        stories.append(story)

    return stories


def validate_dataset_story_index(stories_root: str | Path) -> dict[str, Path]:
    stories_root_path = Path(stories_root)
    if not stories_root_path.exists():
        raise FileNotFoundError(
            f"No existe el directorio base de historias del dataset: {stories_root_path}"
        )

    seen_ids: dict[str, Path] = {}
    for bucket in DATASET_STORY_BUCKETS:
        bucket_dir = stories_root_path / bucket
        if not bucket_dir.exists():
            continue
        for story_file in sorted(bucket_dir.glob("*.md")):
            story = load_story_markdown(story_file)
            story_id = story["metadata"]["id"]
            previous = seen_ids.get(story_id)
            if previous is not None:
                _raise_duplicate_story_id_error(story_id, story_file, previous)
            seen_ids[story_id] = story_file

    return seen_ids


def update_story_markdown_state(story_path: str | Path, new_state: str) -> str:
    path = Path(story_path)
    path_label = str(path)
    normalized_state = _normalize_story_state(new_state, path_label=path_label)
    lines = path.read_text(encoding="utf-8").splitlines()
    _, end_idx = _parse_frontmatter(lines, path_label)

    updated = False
    for index in range(1, end_idx):
        raw_line = lines[index]
        if raw_line.strip().lower().startswith("estado:"):
            lines[index] = f"estado: {normalized_state}"
            updated = True
            break

    if not updated:
        raise ValueError(f"{path_label}: no se encontro el campo 'estado' en el frontmatter")

    return "\n".join(lines).strip() + "\n"


def archive_story_file(
    story_path: str | Path,
    archive_dir: str | Path,
    *,
    archive_state: str = "archived",
) -> Path:
    source_path = Path(story_path)
    destination_dir = Path(archive_dir)
    destination_path = destination_dir / source_path.name

    if not source_path.exists():
        raise FileNotFoundError(f"No existe la historia a archivar: {source_path}")
    if destination_path.exists():
        raise FileExistsError(
            f"No se puede archivar {source_path.name} porque ya existe en archive: {destination_path}"
        )

    destination_dir.mkdir(parents=True, exist_ok=True)
    archived_content = update_story_markdown_state(source_path, archive_state)
    destination_path.write_text(archived_content, encoding="utf-8")
    source_path.unlink()
    return destination_path
