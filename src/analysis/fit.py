"""Local fit analysis. Uses only the stored profile and the offer text.

Nothing is sent to an external model. Missing evidence stays a gap.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9+#.]{3,}")


def _haystack(offer: dict) -> str:
    parts = (
        offer.get("job_title") or "",
        offer.get("description") or "",
        offer.get("location") or "",
        offer.get("company_name") or "",
    )
    return " ".join(parts).lower()


def _skill_present(skill: str, text: str) -> bool:
    cleaned = skill.strip().lower()
    if len(cleaned) < 2:
        return False
    if cleaned in text:
        return True
    tokens = set(_TOKEN.findall(cleaned))
    hay_tokens = set(_TOKEN.findall(text))
    if not tokens:
        return False
    return tokens <= hay_tokens


def analyze_fit(profile: dict, offer: dict) -> dict:
    """Score overlap between approved bridge skills and this offer."""
    text = _haystack(offer)
    matched: list[str] = []
    gaps: list[str] = []
    bridge = profile.get("bridge") or []
    if not isinstance(bridge, list):
        bridge = []

    counted = 0
    for item in bridge:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if not skill or not evidence:
            continue
        counted += 1
        line = f"{skill}: {evidence}"
        if _skill_present(skill, text):
            matched.append(line)
        else:
            gaps.append(skill)

    described = bool((offer.get("description") or "").strip())
    if counted:
        score = round(100 * len(matched) / counted)
    else:
        score = 0
        gaps.append("El perfil no tiene habilidades puente con evidencia.")
    if not described:
        score = min(score, 35)
        gaps.append("La oferta no tiene descripcion guardada; el encaje es incompleto.")

    anchors = profile.get("anchors") if isinstance(profile.get("anchors"), dict) else {}
    draft = _draft(profile, offer, matched, anchors)
    summary = _summary(offer, matched, gaps, score)
    return {
        "fit_score": max(0, min(score, 100)),
        "fit_summary": summary,
        "gap_notes": "\n".join(f"- {gap}" for gap in gaps),
        "draft_body": draft,
        "matched": matched,
        "gaps": gaps,
    }


def _summary(offer: dict, matched: list[str], gaps: list[str], score: int) -> str:
    title = offer.get("job_title") or "esta oferta"
    company = offer.get("company_name") or "la empresa"
    if matched:
        head = f"Encaje {score}/100 con {title} en {company}."
        body = "Evidencia que aparece en la oferta: " + "; ".join(matched) + "."
    else:
        head = f"Encaje {score}/100. No hay habilidades puente que coincidan con {title}."
        body = "Conviene no enviar esta candidatura hasta tener una prueba concreta."
    if gaps:
        body += " Huecos: " + ", ".join(gaps) + "."
    return f"{head} {body}"


def _draft(profile: dict, offer: dict, matched: list[str], anchors: dict) -> str:
    """Letter built only from fields the user already stored."""
    title = offer.get("job_title") or "el puesto"
    company = offer.get("company_name") or "vuestra empresa"
    origin_role = profile.get("origin_role") or "mi rol anterior"
    origin_sector = profile.get("origin_sector") or "otro sector"
    lines = [
        "Hola,",
        "",
        f"Me interesa {title} en {company}.",
        f"Vengo de {origin_role} en {origin_sector}.",
        "",
    ]
    if matched:
        lines.append("Lo que ya puedo demostrar y encaja con esta oferta:")
        lines.extend(f"- {item}" for item in matched)
        lines.append("")
    else:
        lines.append(
            "Todavia no tengo una evidencia directa que coincida con los requisitos visibles."
        )
        lines.append("")
    why_change = str(anchors.get("why_change") or "").strip()
    bring = str(anchors.get("what_you_bring") or "").strip()
    if why_change:
        lines.extend([why_change, ""])
    if bring:
        lines.extend([bring, ""])
    highlights = str(profile.get("origin_highlights") or "").strip()
    if highlights:
        lines.extend(["Contexto que ya esta en mi perfil:", highlights, ""])
    lines.append("Gracias por leer la candidatura.")
    return "\n".join(lines)
