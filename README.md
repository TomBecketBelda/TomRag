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
