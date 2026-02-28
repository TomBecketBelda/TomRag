"""
chat_rag.py — Chat con RAG reutilizable desde consola o desde Flask.

Requisito previo: ejecuta primero `python3 indexar.py`
"""

import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer
from llama_cpp import Llama

# Configuración
ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = str(ROOT_DIR / "modelos" / "Llama-3.2-1B-Instruct-Q4_K_M.gguf")
DB_PATH = str(ROOT_DIR / "vectordb")
N_RESULTADOS = 3
MAX_TOKENS = 512
TEMPERATURE = 0.3

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


def generar_respuesta(pregunta: str) -> dict:
    """Genera respuesta con RAG y devuelve texto + fuentes."""
    inicializar_modelos()
    pregunta = (pregunta or "").strip()
    if not pregunta:
        return {"respuesta": "Escribe una pregunta.", "fuentes": []}

    if total_docs > 0:
        contexto, fuentes = buscar_contexto(pregunta)
        system_prompt = (
            "Eres un asistente útil. Responde SIEMPRE en español.\n"
            "Usa ÚNICAMENTE la siguiente información para responder. "
            "Si la respuesta no está en el contexto, dilo claramente.\n\n"
            f"CONTEXTO:\n{contexto}"
        )
    else:
        fuentes = []
        system_prompt = "Eres un asistente útil que responde siempre en español."

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
    mensaje = respuesta["choices"][0]["message"]["content"].strip()
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
