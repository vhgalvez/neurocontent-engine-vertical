import re
from typing import Any


NEGATION_PATTERNS = (
    " sin ",
    " no ",
    " evitar ",
    " nunca ",
    " jamas ",
)


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _contains_any(text: str, options: tuple[str, ...]) -> bool:
    return any(option in text for option in options)


def _detect_gender(lowered: str) -> str:
    if _contains_any(lowered, ("voz masculina", "masculina", "hombre", "masculino")):
        return "masculina"
    if _contains_any(lowered, ("voz femenina", "femenina", "mujer", "femenino")):
        return "femenina"
    return ""


def _detect_age(lowered: str) -> str:
    range_match = re.search(r"(\d{2}\s*(?:a|-)\s*\d{2}\s*años)", lowered)
    if range_match:
        return range_match.group(1).replace("-", " a ")
    if "adulto" in lowered or "adulta" in lowered:
        return "adulta"
    if "joven" in lowered:
        return "joven"
    if "madura" in lowered or "maduro" in lowered:
        return "madura"
    return ""


def _detect_spanish_variant(lowered: str) -> str:
    if "español de españa" in lowered or "espanol de espana" in lowered:
        return "en español de España"
    if "acento español neutro" in lowered or "acento espanol neutro" in lowered:
        return "en español con acento español neutro"
    if "español neutro" in lowered or "espanol neutro" in lowered:
        return "en español neutro"
    if "español" in lowered or "espanol" in lowered:
        return "en español"
    return ""


def _detect_timbre(lowered: str) -> str:
    if "medio-grave" in lowered or "mediograve" in lowered:
        return "Timbre medio-grave y estable."
    if "grave" in lowered:
        return "Timbre grave y estable."
    if "cálida" in lowered or "calida" in lowered:
        return "Timbre cálido y estable."
    if "firme" in lowered:
        return "Timbre firme y estable."
    return "Timbre estable y natural."


def _detect_delivery_traits(lowered: str) -> list[str]:
    traits: list[str] = []
    if "dicción clara" in lowered or "diccion clara" in lowered or "clara" in lowered:
        traits.append("dicción clara")
    if "natural" in lowered or "fluida" in lowered or "fluido" in lowered:
        traits.append("ritmo natural")
    if "profesional" in lowered:
        traits.append("tono profesional")
    if "sobrio" in lowered:
        traits.append("tono sobrio")
    if "creíble" in lowered or "creible" in lowered:
        traits.append("sonido creíble")
    if "inteligible" in lowered or "inteligibilidad" in lowered:
        traits.append("alta inteligibilidad")
    return traits


def analyze_voice_design_prompt(description: str) -> dict[str, Any]:
    normalized = normalize_text(description)
    lowered = f" {normalized.casefold()} "
    negation_count = sum(lowered.count(pattern) for pattern in NEGATION_PATTERNS)
    sentence_count = len([chunk for chunk in re.split(r"[.!?]+", normalized) if chunk.strip()])
    word_count = len(normalized.split())

    issues: list[str] = []
    if word_count > 55:
        issues.append("description_too_long")
    if negation_count >= 3:
        issues.append("negation_heavy")
    if sentence_count >= 4:
        issues.append("too_many_constraints")
    if word_count > 0 and sentence_count == 1 and "," in normalized:
        issues.append("comma_stacked_constraints")

    if len(issues) >= 3:
        risk = "high"
    elif issues:
        risk = "medium"
    else:
        risk = "low"

    return {
        "risk": risk,
        "issues": issues,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "negation_count": negation_count,
    }


def build_identity_locked_voice_instruct(description: str) -> str:
    normalized = normalize_text(description)
    lowered = normalized.casefold()

    gender = _detect_gender(lowered)
    age = _detect_age(lowered)
    language = _detect_spanish_variant(lowered)

    subject_bits = ["Voz"]
    if gender:
        subject_bits.append(gender)
    if age:
        if age == "adulta":
            subject_bits.append("adulta")
        elif age == "madura":
            subject_bits.append("madura")
        elif age == "joven":
            subject_bits.append("joven")
        else:
            subject_bits.append(f"de {age}")
    else:
        subject_bits.append("adulta")
    if language:
        subject_bits.append(language)
    identity_sentence = " ".join(subject_bits).replace("  ", " ").strip() + "."

    timbre_sentence = _detect_timbre(lowered)
    delivery_traits = _detect_delivery_traits(lowered)
    if delivery_traits:
        delivery_sentence = ", ".join(delivery_traits[:4]).capitalize() + "."
    else:
        delivery_sentence = "Dicción clara, ritmo natural y tono profesional sobrio."

    stability_sentence = (
        "Mantener el mismo sexo aparente, edad aparente y timbre entre clips. "
        "Priorizar estabilidad vocal sobre estilo."
    )
    expression_sentence = "Expresividad contenida, energía media estable y sin cambios amplios de color vocal."

    return " ".join(
        part
        for part in [
            identity_sentence,
            timbre_sentence,
            delivery_sentence,
            stability_sentence,
            expression_sentence,
        ]
        if part
    ).strip()


def prepare_voice_design_instruct(description: str) -> dict[str, Any]:
    normalized_description = normalize_text(description)
    analysis = analyze_voice_design_prompt(normalized_description)
    effective_instruct = build_identity_locked_voice_instruct(normalized_description)
    return {
        "raw_description": normalized_description,
        "effective_instruct": effective_instruct,
        "analysis": analysis,
    }
