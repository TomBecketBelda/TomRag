# TomRag

## Modelo LLM (Llama 8B)

Este proyecto está configurado para usar por defecto:

- `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`
- Ruta esperada: `modelos/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`
- Fuente: [bartowski/Meta-Llama-3.1-8B-Instruct-GGUF](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF)

Descarga rápida (si tienes `huggingface-cli`):

```bash
huggingface-cli download \
  bartowski/Meta-Llama-3.1-8B-Instruct-GGUF \
  Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf \
  --local-dir modelos
```

Opcional: usar otra ruta de modelo

```bash
export LLAMA_MODEL_PATH="/ruta/a/tu/modelo.gguf"
```

## Fallback a internet cuando RAG no encuentra contexto

Si no hay contexto útil en tu base vectorial, el chat puede consultar web como respaldo.

Variables opcionales:

```bash
export ENABLE_WEB_FALLBACK=1      # 1=activo, 0=desactivado
export WEB_MAX_RESULTADOS=3       # número de snippets web a usar
export WEB_TIMEOUT_S=8            # timeout de cada petición web
```
