from llama_cpp import Llama
from pathlib import Path

# ─────────────────────────────────────────────
# Configuración del modelo
# ─────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = str(ROOT_DIR / "modelos" / "Llama-3.2-1B-Instruct-Q4_K_M.gguf")

print("⏳ Cargando modelo... (puede tardar unos segundos)")

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,       # Tamaño del contexto en tokens
    n_threads=8,      # Hilos de CPU (ajusta según tu Mac)
    n_gpu_layers=-1,  # -1 = usar Metal GPU al máximo (Apple Silicon M1/M2/M3)
    verbose=False,
)

print("✅ Modelo cargado. Escribe 'salir' para terminar.\n")

# ─────────────────────────────────────────────
# Historial de conversación
# ─────────────────────────────────────────────
historial = [
    {
        "role": "system",
        "content": "Eres un asistente útil que responde siempre en español de forma clara y concisa.",
    }
]

# ─────────────────────────────────────────────
# Bucle de chat
# ─────────────────────────────────────────────
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

    historial.append({"role": "user", "content": pregunta})

    respuesta = llm.create_chat_completion(
        messages=historial,
        max_tokens=512,
        temperature=0.7,
        stop=["<|eot_id|>"],  # Token de fin para Llama 3.2
    )

    mensaje = respuesta["choices"][0]["message"]["content"].strip()
    historial.append({"role": "assistant", "content": mensaje})

    print(f"\nAsistente: {mensaje}\n")
