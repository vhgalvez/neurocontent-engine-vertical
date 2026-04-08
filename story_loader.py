from pathlib import Path
from typing import Any

FRONTMATTER_DELIM = "---"

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


def _validate_required_sections(sections: dict[str, str], path_label: str) -> None:
    missing = [section for section in REQUIRED_BODY_SECTIONS if not _normalize_value(sections.get(section))]
    if missing:
        pretty_missing = ", ".join(f"## {section.title()}" if section != "title" else "# Titulo" for section in missing)
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
        metadata.get("content_orientation") or (
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

    _validate_required_metadata(metadata, path_label)
    _validate_required_sections(sections, path_label)

    normalized_metadata = _normalize_story_metadata(metadata, sections)

    story = {
        "metadata": normalized_metadata,
        "title": _normalize_value(sections.get("title")),
        "hook": _normalize_value(sections.get("hook")),
        "historia": _normalize_value(sections.get("historia")),
        "cta": _normalize_value(sections.get("cta")),
        "visual_notes": _normalize_value(sections.get("visual_notes")),
        "prohibido": _normalize_value(sections.get("prohibido") or normalized_metadata.get("prohibido")),
    }

    if not story["historia"]:
        raise ValueError(f"{path_label}: la historia no puede estar vacia")

    return story


def load_story_markdown(path: str | Path) -> dict[str, Any]:
    story_path = Path(path)
    return parse_story_markdown(
        story_path.read_text(encoding="utf-8"),
        path_label=str(story_path),
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
            raise ValueError(
                f"ID duplicado en historias Markdown: {source_id} aparece en {previous} y {story_file}"
            )
        seen_ids[source_id] = story_file
        stories.append(story)

    return stories
