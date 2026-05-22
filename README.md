# Dark Monster Generator

App sencilla de Streamlit que recibe un prompt y genera imágenes usando
[fal.ai](https://fal.ai) (modelo FLUX.1 [schnell]). Cada imagen generada se guarda
en [Supabase](https://supabase.com) (Storage + base de datos) y se puede revisar en
una galería.

El código está separado por responsabilidad:

- `generator.py` — lógica de generación con fal.ai.
- `storage.py` — persistencia en Supabase (subida a Storage + registro en la tabla).
- `app.py` — interfaz de Streamlit (pestañas *Generate* y *Gallery*).

El proyecto usa [uv](https://docs.astral.sh/uv/) como gestor de entorno y dependencias.

## Setup

```bash
# 1. Instalar dependencias (crea el entorno .venv automáticamente)
uv sync

# 2. Configurar las claves
cp .env.example .env
# edita .env con:
#   FAL_KEY        -> https://fal.ai/dashboard/keys
#   SUPABASE_URL   -> Supabase > Project Settings > Data API (URL del proyecto)
#   SUPABASE_KEY   -> Supabase > Project Settings > API Keys (service_role)
```

### Configurar Supabase (pasos manuales, una sola vez)

1. **Crear la tabla**: abre *Supabase > SQL Editor* y ejecuta el contenido de
   [`supabase_setup.sql`](supabase_setup.sql).
2. **Crear el bucket**: en *Supabase > Storage*, crea un bucket **público**
   llamado `monsters`.

> Se usa la clave `service_role` porque la app corre en el servidor (Streamlit),
> nunca en el navegador. No la expongas en código cliente.

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
