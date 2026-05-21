# Dark Monster Generator

App sencilla de Streamlit que recibe un prompt y genera imágenes usando
[fal.ai](https://fal.ai) (modelo FLUX.1 [schnell]).

La lógica de generación (`generator.py`) está separada de la interfaz (`app.py`),
para que puedas reutilizarla desde scripts o tests sin Streamlit.

El proyecto usa [uv](https://docs.astral.sh/uv/) como gestor de entorno y dependencias.

## Setup

```bash
# 1. Instalar dependencias (crea el entorno .venv automáticamente)
uv sync

# 2. Configurar la API key
cp .env.example .env
# edita .env y pon tu FAL_KEY (la obtienes en https://fal.ai/dashboard/keys)
```

## Uso

```bash
uv run streamlit run app.py
```

Escribe un prompt (por ejemplo `a dark monster in a foggy forest`), pulsa
**Generar** y verás la imagen.

### Probar solo la lógica (sin UI)

```bash
uv run python generator.py
```

Imprime la URL de una imagen de ejemplo.
