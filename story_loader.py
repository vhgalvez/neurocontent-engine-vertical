import os
from pathlib import Path
from typing import Dict, Any, List

FRONTMATTER_DELIM = '---'


def parse_story_frontmatter(content: str) -> Dict[str, Any]:
    """Extrae el frontmatter YAML simple y el cuerpo de un archivo Markdown de historia."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        raise ValueError("El archivo no comienza con frontmatter ---")
    # Buscar fin del frontmatter
    end_idx = 1
    while end_idx < len(lines) and lines[end_idx].strip() != FRONTMATTER_DELIM:
        end_idx += 1
    if end_idx == len(lines):
        raise ValueError("No se encontró cierre de frontmatter ---")
    # Parsear frontmatter
    meta = {}
    for line in lines[1:end_idx]:
        if ':' in line:
            key, value = line.split(':', 1)
            meta[key.strip()] = value.strip()
    # El resto es el cuerpo
    body = '\n'.join(lines[end_idx+1:])
    # Extraer secciones del cuerpo
    sections = {}
    current = None
    buffer = []
    for line in body.splitlines():
        if line.startswith('# '):
            if current:
                sections[current] = '\n'.join(buffer).strip()
                buffer = []
            current = 'title'
            buffer.append(line[2:].strip())
        elif line.startswith('## '):
            if current:
                sections[current] = '\n'.join(buffer).strip()
                buffer = []
            current = line[3:].strip().lower().replace(' ', '_')
        else:
            buffer.append(line)
    if current:
        sections[current] = '\n'.join(buffer).strip()
    # Normalizar salida
    return {
        'metadata': meta,
        'title': sections.get('title', ''),
        'hook': sections.get('hook', ''),
        'historia': sections.get('historia', ''),
        'cta': sections.get('cta', ''),
        'visual_notes': sections.get('visual_notes', ''),
        'prohibido': sections.get('prohibido', ''),
    }


def load_story_markdown(path: str | Path) -> Dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        content = f.read()
    return parse_story_frontmatter(content)


def load_all_stories(directory: str | Path) -> List[Dict[str, Any]]:
    dir_path = Path(directory)
    stories = []
    for file in sorted(dir_path.glob('*.md')):
        try:
            story = load_story_markdown(file)
            stories.append(story)
        except Exception as e:
            print(f"Error cargando {file}: {e}")
    return stories
