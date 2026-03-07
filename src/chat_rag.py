"""
chat_rag.py — Chat con RAG reutilizable desde consola o desde Flask.

Requisito previo: ejecuta primero `python3 indexar.py`
"""

import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer
from llama_cpp import Llama
import os
import json
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Configuración
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = ROOT_DIR / "modelos" / "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
MODEL_PATH = os.getenv("LLAMA_MODEL_PATH", str(DEFAULT_MODEL_PATH))
DB_PATH = str(ROOT_DIR / "vectordb")
N_RESULTADOS = 3
MAX_TOKENS = 512
TEMPERATURE = 0.3
ENABLE_WEB_FALLBACK = os.getenv("ENABLE_WEB_FALLBACK", "1").lower() not in ("0", "false", "no")
WEB_MAX_RESULTADOS = int(os.getenv("WEB_MAX_RESULTADOS", "3"))
WEB_TIMEOUT_S = int(os.getenv("WEB_TIMEOUT_S", "8"))

# Estado global cargado de forma diferida (lazy load)
embedder = None
llm = None
coleccion = None
total_docs = 0
_inicializado = False


def inicializar_modelos() -> None:
    """Carga modelos y base vectorial una sola vez."""
    global embedder, llm, coleccion, total_docs, _inicializado
    if _inicializado:
        return

    print("⏳ Cargando modelos (puede tardar unos segundos)...")

    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    if not Path(MODEL_PATH).exists():
        raise FileNotFoundError(
            "No se encontró el modelo GGUF 8B en:\n"
            f"  {MODEL_PATH}\n\n"
            "Descárgalo desde Hugging Face:\n"
            "  https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF\n"
            "Archivo recomendado:\n"
            "  Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf\n\n"
            "También puedes usar otra ruta con la variable de entorno LLAMA_MODEL_PATH."
        )

    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=4096,
        n_threads=8,
        n_gpu_layers=-1,
        verbose=False,
    )

    client = chromadb.PersistentClient(path=DB_PATH)
    coleccion = client.get_or_create_collection("documentos")
    total_docs = coleccion.count()

    if total_docs == 0:
        print("\n⚠️  La base de datos está vacía.")
        print("   Ejecuta primero: python3 indexar.py\n")
    else:
        print(f"✅ Listo. Base de datos con {total_docs} fragmentos indexados.\n")

    _inicializado = True


def buscar_contexto(pregunta: str) -> tuple[str, list[str]]:
    """Busca fragmentos relevantes y devuelve contexto + fuentes."""
    inicializar_modelos()
    if total_docs == 0:
        return "", []

    embedding = embedder.encode([pregunta]).tolist()
    resultados = coleccion.query(
        query_embeddings=embedding,
        n_results=min(N_RESULTADOS, total_docs),
    )
    fragmentos = resultados["documents"][0]
    ids = resultados["ids"][0]
    fuentes = sorted({id_.rsplit("_", 1)[0] for id_ in ids})
    return "\n\n---\n\n".join(fragmentos), fuentes


def buscar_contexto_web(pregunta: str, max_resultados: int = WEB_MAX_RESULTADOS) -> tuple[str, list[str]]:
    """
    Busca contexto breve en internet usando varias fuentes.
    Se usa como fallback cuando RAG no tiene contexto.
    """
    fragmentos: list[str] = []
    fuentes: list[str] = []

    def add_fragment(texto: str, fuente: str = "") -> None:
        """Añade un fragmento/fuente evitando duplicados y valores vacíos."""
        t = (texto or "").strip()
        if not t:
            return
        if t not in fragmentos:
            fragmentos.append(t)
        if fuente and fuente not in fuentes:
            fuentes.append(fuente)

    # 1) DuckDuckGo Instant Answer (rápido pero a veces vacío)
    try:
        url = (
            "https://api.duckduckgo.com/"
            f"?q={quote_plus(pregunta)}&format=json&no_html=1&skip_disambig=1"
        )
        req = Request(
            url,
            headers={
                "User-Agent": "TomRag/1.0",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            },
        )
        with urlopen(req, timeout=WEB_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except (HTTPError, URLError, TimeoutError, ValueError):
        data = {}

    abstract_text = (data.get("AbstractText") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    if abstract_text:
        add_fragment(abstract_text, abstract_url)

    related = data.get("RelatedTopics") or []
    for topic in related:
        if len(fragmentos) >= max_resultados:
            break
        if isinstance(topic, dict) and topic.get("Topics"):
            for nested in (topic.get("Topics") or []):
                if len(fragmentos) >= max_resultados:
                    break
                text = (nested.get("Text") or "").strip()
                first_url = (nested.get("FirstURL") or "").strip()
                if text:
                    add_fragment(text, first_url)
        else:
            text = (topic.get("Text") or "").strip() if isinstance(topic, dict) else ""
            first_url = (topic.get("FirstURL") or "").strip() if isinstance(topic, dict) else ""
            if text:
                add_fragment(text, first_url)

    # 2) Wikipedia ES (más estable para preguntas generales)
    if len(fragmentos) < max_resultados:
        try:
            url = (
                "https://es.wikipedia.org/w/api.php"
                f"?action=query&list=search&srsearch={quote_plus(pregunta)}"
                "&utf8=1&format=json&srlimit=3"
            )
            req = Request(
                url,
                headers={
                    "User-Agent": "TomRag/1.0",
                    "Accept": "application/json",
                    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                },
            )
            with urlopen(req, timeout=WEB_TIMEOUT_S) as resp:
                wiki_data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except (HTTPError, URLError, TimeoutError, ValueError):
            wiki_data = {}

        search_items = (
            ((wiki_data.get("query") or {}).get("search") or [])
            if isinstance(wiki_data, dict)
            else []
        )
        for item in search_items:
            if len(fragmentos) >= max_resultados:
                break
            title = (item.get("title") or "").strip()
            if not title:
                continue
            try:
                summary_url = (
                    "https://es.wikipedia.org/api/rest_v1/page/summary/"
                    f"{quote_plus(title)}"
                )
                req = Request(
                    summary_url,
                    headers={
                        "User-Agent": "TomRag/1.0",
                        "Accept": "application/json",
                    },
                )
                with urlopen(req, timeout=WEB_TIMEOUT_S) as resp:
                    summary_data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            except (HTTPError, URLError, TimeoutError, ValueError):
                continue

            extract = (summary_data.get("extract") or "").strip()
            page_url = (
                ((summary_data.get("content_urls") or {}).get("desktop") or {}).get("page")
                or f"https://es.wikipedia.org/wiki/{quote_plus(title)}"
            )
            if extract:
                add_fragment(extract, page_url)

    if not fragmentos:
        return "", []
    return "\n\n---\n\n".join(fragmentos[:max_resultados]), fuentes[:max_resultados]


def _respuesta_sin_info(texto: str) -> bool:
    """Detecta si el modelo respondió explícitamente que no tiene información."""
    t = (texto or "").lower()
    patrones = [
        "no está en el contexto",
        "no dispongo de",
        "no tengo información",
        "no encuentro información",
        "no se menciona",
        "no puedo responder con la información",
    ]
    return any(p in t for p in patrones)


def generar_respuesta(pregunta: str) -> dict:
    """Genera respuesta con RAG y devuelve texto + fuentes."""
    inicializar_modelos()
    pregunta = (pregunta or "").strip()
    if not pregunta:
        return {"respuesta": "Escribe una pregunta.", "fuentes": []}

    origen_contexto = "none"
    contexto = ""
    fuentes = []

    if total_docs > 0:
        contexto, fuentes = buscar_contexto(pregunta)
        if contexto.strip():
            origen_contexto = "rag"

    if not contexto.strip() and ENABLE_WEB_FALLBACK:
        contexto, fuentes = buscar_contexto_web(pregunta)
        if contexto.strip():
            origen_contexto = "web"

    def _resolver(contexto_local: str, origen_local: str) -> str:
        """Construye el prompt según el origen del contexto y consulta el LLM."""
        if contexto_local.strip():
            if origen_local == "web":
                instrucciones_fuente = (
                    "Usa ÚNICAMENTE la siguiente información web para responder. "
                    "Si no es suficiente, dilo claramente.\n\n"
                )
            else:
                instrucciones_fuente = (
                    "Usa ÚNICAMENTE la siguiente información para responder. "
                    "Si la respuesta no está en el contexto, dilo claramente.\n\n"
                )
            system_prompt = (
                "Eres un asistente útil. Responde SIEMPRE en español.\n"
                f"{instrucciones_fuente}"
                f"CONTEXTO:\n{contexto_local}"
            )
        else:
            system_prompt = (
                "Eres un asistente útil que responde siempre en español. "
                "Si no tienes información confiable, dilo claramente."
            )

        mensajes = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pregunta},
        ]
        respuesta = llm.create_chat_completion(
            messages=mensajes,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stop=["<|eot_id|>"],
        )
        return respuesta["choices"][0]["message"]["content"].strip()

    mensaje = _resolver(contexto, origen_contexto)

    # Segundo intento con web si el primero indica falta de información.
    if ENABLE_WEB_FALLBACK and origen_contexto != "web" and _respuesta_sin_info(mensaje):
        contexto_web, fuentes_web = buscar_contexto_web(pregunta)
        if contexto_web.strip():
            mensaje = _resolver(contexto_web, "web")
            fuentes = fuentes_web

    return {"respuesta": mensaje, "fuentes": fuentes}


def chat_cli() -> None:
    """Chat por terminal."""
    inicializar_modelos()
    print("Chat RAG iniciado. Escribe 'salir' para terminar.\n")

    while True:
        try:
            pregunta = input("Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 ¡Hasta luego!")
            break

        if not pregunta:
            continue

        if pregunta.lower() in ("salir", "exit", "quit"):
            print("👋 ¡Hasta luego!")
            break

        salida = generar_respuesta(pregunta)
        if salida["fuentes"]:
            print(f"🔍 Fuentes consultadas: {', '.join(salida['fuentes'])}")
        print(f"\n🤖 Asistente: {salida['respuesta']}\n")


if __name__ == "__main__":
    chat_cli()
