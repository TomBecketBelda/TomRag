from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, StateGraph


class EmotionState(TypedDict, total=False):
    message: str
    emotion: str
    confidence: float
    rationale: str
    meter_score: int
    meter_label: str


@dataclass(frozen=True)
class EmotionProfile:
    emotion: str
    confidence: float
    rationale: str


_KEYWORDS: dict[str, tuple[str, ...]] = {
    "alegria": ("feliz", "genial", "contento", "alegre", "gracias", "perfecto", "excelente"),
    "tristeza": ("triste", "deprimido", "mal", "agotado", "llorar", "solo"),
    "enojo": ("enfadado", "enojado", "rabia", "odio", "molesto", "indignado"),
    "miedo": ("miedo", "ansioso", "ansiedad", "nervioso", "preocupado", "temor"),
    "calma": ("tranquilo", "calma", "relajado", "sereno", "en paz"),
}

_METER_BY_EMOTION: dict[str, tuple[int, str]] = {
    "alegria": (84, "alto"),
    "calma": (68, "medio"),
    "miedo": (38, "bajo"),
    "tristeza": (28, "bajo"),
    "enojo": (18, "muy bajo"),
    "neutral": (55, "medio"),
}


def _clasificar_texto(message: str) -> EmotionProfile:
    texto = (message or "").strip().lower()
    if not texto:
        return EmotionProfile("neutral", 0.0, "Mensaje vacío")

    puntajes = {emocion: 0 for emocion in _KEYWORDS}
    for emocion, palabras in _KEYWORDS.items():
        for palabra in palabras:
            if palabra in texto:
                puntajes[emocion] += 1

    mejor_emocion = max(puntajes, key=puntajes.get)
    mejor_puntaje = puntajes[mejor_emocion]

    if mejor_puntaje == 0:
        # Ajustes simples por puntuación para mensajes sin palabras clave.
        if "!" in texto:
            return EmotionProfile("alegria", 0.58, "Tono exclamativo positivo/energético")
        if "?" in texto:
            return EmotionProfile("miedo", 0.52, "Tono dubitativo/interrogativo")
        return EmotionProfile("neutral", 0.5, "Sin señales emocionales claras")

    confianza = min(0.95, 0.6 + (mejor_puntaje * 0.12))
    razon = f"Coincidencias detectadas para emoción '{mejor_emocion}'"
    return EmotionProfile(mejor_emocion, confianza, razon)


def classify_emotion_node(state: EmotionState) -> EmotionState:
    profile = _clasificar_texto(state.get("message", ""))
    return {
        "emotion": profile.emotion,
        "confidence": round(profile.confidence, 2),
        "rationale": profile.rationale,
    }


def mediate_emotion_meter_node(state: EmotionState) -> EmotionState:
    emocion = state.get("emotion", "neutral")
    score, label = _METER_BY_EMOTION.get(emocion, _METER_BY_EMOTION["neutral"])

    # Ajuste final por confianza: a menor confianza, más cerca de neutral (50).
    confianza = float(state.get("confidence", 0.5))
    score_ajustado = int(round((score * confianza) + (50 * (1 - confianza))))
    score_ajustado = max(0, min(100, score_ajustado))

    return {
        "meter_score": score_ajustado,
        "meter_label": label,
    }


def _build_graph():
    graph = StateGraph(EmotionState)
    graph.add_node("classify_emotion", classify_emotion_node)
    graph.add_node("mediate_emotion_meter", mediate_emotion_meter_node)
    graph.set_entry_point("classify_emotion")
    graph.add_edge("classify_emotion", "mediate_emotion_meter")
    graph.add_edge("mediate_emotion_meter", END)
    return graph.compile()


EMOTION_METER_GRAPH = _build_graph()


def run_emotion_meter(message: str) -> dict:
    final_state = EMOTION_METER_GRAPH.invoke({"message": message})
    return {
        "emotion": final_state.get("emotion", "neutral"),
        "confidence": float(final_state.get("confidence", 0.5)),
        "rationale": final_state.get("rationale", ""),
        "score": int(final_state.get("meter_score", 50)),
        "label": final_state.get("meter_label", "medio"),
    }
