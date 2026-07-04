# Street Monster — Dark Monster Generator

Instalación para el festival Golden Days (Dark Gallery CPH): un monstruo
colectivo que evoluciona durante el día a partir de las respuestas de los
visitantes a un cuestionario. Cada día nace un monstruo nuevo; cada
contribución lo transforma.

Construido con [Streamlit](https://streamlit.io), [fal.ai](https://fal.ai)
(FLUX schnell para generar, FLUX Kontext para transformar, Claude vía
OpenRouter como curador) y [Supabase](https://supabase.com) (Storage + BD).

## Cómo funciona

```
Visitante rellena el cuestionario
        │
        ▼
curator.update_genome()      ← tablas emoción→anatomía (Rika) y
   acumula la submission        habilidades→efecto visual (Kim),
   en el GENOMA del día         con pesos por parte del cuerpo
        │
        ▼
¿Primera del día? ──sí──► generate_image(descripción completa)   [initial]
        │no
¿4+ ediciones desde el último anclaje?
        │                 ──sí──► generate_image(descr. completa) [reanchor]
        │no                       (la edición iterativa degrada ~5 pasadas)
        ▼
curator.build_edit_instruction()  → LLM traduce la submission a UNA
        │                           instrucción de cambio anatómico
        ▼
generator.edit_image()  → FLUX Kontext transforma la imagen actual  [edit]
        │
        ▼
Supabase: genoma actualizado (monster_state) + versión guardada (generations)
```

El código está separado por responsabilidad:

- `curator.py` — genoma colectivo: lookup tables emoción→anatomía y
  habilidad→efecto, acumulación estadística ponderada, y LLM que traduce
  el input libre al vocabulario visual del proyecto (con fallback
  determinista si el LLM falla).
- `generator.py` — generación (FLUX schnell + plantilla de estilo fija) y
  transformación (FLUX Kontext + guardián de estilo en cada edición).
- `storage.py` — Supabase: submissions, estado diario del monstruo
  (genoma) e historial de versiones.
- `app.py` — Streamlit: cuestionario, monstruo del día con su evolución,
  y galería por días.

El estilo visual (radiografía/MRI translúcida, paleta monocroma fría con
acentos cian/rojo, overlay HUD médico sci-fi, fondo negro) está fijado por
plantilla en `generator.py` y NO depende del input del usuario.

## Setup

```bash
# 1. Instalar dependencias (crea el entorno .venv automáticamente)
uv sync

# 2. Configurar las claves
cp .env.example .env
# edita .env con:
#   FAL_KEY        -> https://fal.ai/dashboard/keys (cubre imagen + LLM)
#   SUPABASE_URL   -> Supabase > Project Settings > Data API (URL del proyecto)
#   SUPABASE_KEY   -> Supabase > Project Settings > API Keys (service_role)
```

### Configurar Supabase (pasos manuales, una sola vez)

1. **Crear las tablas**: abre *Supabase > SQL Editor* y ejecuta el contenido
   de [`supabase_setup.sql`](supabase_setup.sql). Es idempotente: se puede
   re-ejecutar sin peligro (crea `generations`, `submissions` y
   `monster_state`, y añade columnas si faltan).
2. **Crear el bucket**: en *Supabase > Storage*, crea un bucket **público**
   llamado `monsters`.

> Se usa la clave `service_role` porque la app corre en el servidor
> (Streamlit), nunca en el navegador. No la expongas en código cliente.

## Uso

```bash
uv run streamlit run app.py
```

Páginas: **Contribute** (el cuestionario que alimenta al monstruo),
**Monster** (el monstruo de hoy y su evolución), **Gallery** (días e
iteraciones anteriores con todas sus versiones) y **Data** (vista de
análisis: inputs crudos de los visitantes, genoma acumulado y botón de
reset que archiva el monstruo actual como "Iteration X" y arranca uno
nuevo — pensado para el periodo de testeo).

El curador **ve la imagen actual** del monstruo (visión multimodal, ~$0.005
por edición extra sobre los $0.04 de Kontext), de modo que sus
instrucciones solo referencian anatomía que existe de verdad en la imagen.

### Probar la lógica sin UI

```bash
uv run python curator.py    # genoma + instrucción de edición + descripción
uv run python generator.py  # genera una imagen de ejemplo
```

## Pendiente / siguientes pasos

- Entrenar un **LoRA de estilo** con el board de Pinterest para blindar la
  estética a nivel de modelo (fal `flux-lora-fast-training`, ~$2), y usarlo
  en los re-anclajes.
- Fusionar las imágenes subidas por visitantes en el monstruo (Kontext
  multi-imagen o nano-banana edit).
- Decidir con Kim/Rika cómo reinterpretar los colores elegidos por el
  visitante dentro de la paleta monocroma (propuesta: modulan el color de
  acento).
