# Street Monster — Dark Monster Generator

Instalación para el festival Golden Days (Dark Gallery CPH): un monstruo
colectivo que evoluciona durante el día a partir de las respuestas de los
visitantes a un cuestionario. Cada día nace un monstruo nuevo; cada
contribución lo transforma.

Front en **React** (Vite + Tailwind), API en **FastAPI**, imágenes con
[fal.ai](https://fal.ai) (Krea 2 Large para generar, Qwen Image Edit 2511
para transformar, Claude vía OpenRouter como curador) y
[Supabase](https://supabase.com) (Storage + BD).

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
¿Primera del día / tras reset? ──sí──► generate_image(descr.)     [initial]
        │no
¿3+ ediciones Kontext desde el anclaje?
        │        ──sí──► refresh_image(): img2img de la imagen    [reanchor]
        │no              actual (repinta detalle, conserva identidad)
        ▼
curator.build_edit_plan()  → el LLM VE la imagen y clasifica:
        │
        ├─ "local" ──► segment_region (EVF-SAM, máscara por texto,
        │              cobertura 0.5%-30%) → fill_region (FLUX Fill:
        │              repinta SOLO la zona; el resto queda           [edit]
        │              píxel-idéntico, cero drift)
        │                │ (si falla, cae a ↓)
        └─ "structural" ► edit_image (Kontext pro) con rescate
                          anti-censura (reformular → Kontext dev
                          sin filtro) + match_palette (anti deriva    [edit]
                          cromática; solo los Kontext cuentan
                          para el re-anclaje)
        │
        ▼
Supabase: genoma actualizado (monster_state) + versión guardada (generations)
```

El código está separado por responsabilidad:

- `curator.py` — genoma colectivo: mapeo grupo de emociones→partes del cuerpo
  (con transformación distinta según la familia emocional), acumulación
  estadística ponderada, y LLM que traduce el input libre al vocabulario
  visual del proyecto (con fallback determinista si el LLM falla).
- `generator.py` — generación (Krea 2 Large + plantilla de estilo fija) y
  transformación (Qwen Image Edit 2511 + guardián de estilo en cada edición),
  con los motores anteriores conservados como fallbacks.
- `pipeline.py` — el flujo de una contribución, compartido por la API y los
  scripts de prueba.
- `storage.py` — Supabase: submissions, estado diario del monstruo
  (genoma) e historial de versiones.
- `api.py` — FastAPI: endpoints del cuestionario, del monstruo y del reset.
- `web/` — front en React: cuestionario, monstruo del día, galería y datos.

El estilo visual está fijado por plantilla en `generator.py` y NO depende del
input del usuario. Hay dos: `surgical` (por defecto — fotografía analógica de
un quirófano de los 70, donde el monstruo es el paciente sobre la mesa y las
contribuciones son la cirugía) y `radiograph` (placa de rayos X pálida).

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

### Observabilidad (Logfire)

Cada submission genera una traza en
[Logfire](https://logfire-eu.pydantic.dev/bulacio/dark-monster-generator)
(`process submission` → `build edit instruction` / `build full description` →
`curator llm call` → `edit image` / `generate image`), con el input del
visitante, los prompts generados, el coste del LLM y las URLs de imagen.

Credenciales (una de las dos):

```bash
# desarrollo local (OAuth del CLI, una sola vez):
uv run logfire --base-url='https://logfire-eu.pydantic.dev' auth
uv run logfire --base-url='https://logfire-eu.pydantic.dev' projects use --org 'bulacio' 'dark-monster-generator'

# o en despliegues: añade LOGFIRE_TOKEN a .env (write token del proyecto)
```

Sin credenciales la app funciona igual; simplemente no envía telemetría.

### Configurar Supabase (pasos manuales, una sola vez)

1. **Crear las tablas**: abre *Supabase > SQL Editor* y ejecuta el contenido
   de [`supabase_setup.sql`](supabase_setup.sql). Es idempotente: se puede
   re-ejecutar sin peligro (crea `generations`, `submissions` y
   `monster_state`, y añade columnas si faltan).
2. **Crear el bucket**: en *Supabase > Storage*, crea un bucket **público**
   llamado `monsters`.

> Se usa la clave `service_role` porque solo la usa la API de Python en el
> servidor, nunca el navegador. No la expongas en código cliente.

## Uso

Dos procesos: la API de Python y el front de React.

```bash
uv run uvicorn api:app --reload --port 8000
```

```bash
npm install --prefix web && npm run dev --prefix web
```

La interfaz queda en http://localhost:5173 (Vite hace de proxy de `/api` hacia
el 8000, así que el navegador ve un único origen).

Stack del front: **Vite 8 + React 19 + TypeScript 6**, **Tailwind CSS 4** vía
`@tailwindcss/vite` (sin `tailwind.config.js` ni PostCSS: el tema vive en
`web/src/index.css`) y componentes al estilo shadcn/ui en
`web/src/components/ui/`.

Páginas: **Contribute** (el cuestionario que alimenta al monstruo),
**Monster** (el monstruo de hoy y su evolución), **Gallery** (días e
iteraciones anteriores con todas sus versiones) y **Data** (vista de
análisis: inputs crudos de los visitantes, genoma acumulado y botón de
reset que archiva el monstruo actual como "Iteration X" y arranca uno
nuevo — pensado para el periodo de testeo).

**En móvil solo se ve el cuestionario**: los visitantes responden desde su
teléfono, así que ahí no hay navegación ni el resto de vistas, que son la
superficie de curación en escritorio.

El curador **ve la imagen actual** del monstruo (visión multimodal, ~$0.005
extra por edición), de modo que sus instrucciones solo referencian anatomía
que existe de verdad en la imagen.

## Despliegue en Fly.io

La app se despliega como **un solo contenedor**: el front compilado lo sirve la
propia API, así que hay una única URL y la contraseña cubre también la interfaz.

Mientras la pieza está en desarrollo todo el sitio va detrás de una contraseña
compartida (HTTP Basic: el navegador pide usuario y contraseña; el usuario da
igual, solo se valida la contraseña). Se activa con la variable `APP_PASSWORD`
— si no está definida, no hay contraseña (así el desarrollo local sigue igual).

```bash
fly auth login
fly launch --no-deploy          # solo la primera vez, reutiliza fly.toml

fly secrets set \
  APP_PASSWORD='...' \
  FAL_KEY='...' \
  SUPABASE_URL='...' \
  SUPABASE_KEY='...' \
  LOGFIRE_TOKEN='...'

fly deploy --remote-only        # --remote-only evita necesitar Docker local
```

`LOGFIRE_TOKEN` es opcional: sin él la app funciona igual, solo deja de enviar
telemetría (el OAuth del CLI no sirve dentro del contenedor, hace falta un
write token del proyecto de Logfire).

Detalles de `fly.toml`: región Estocolmo (la más cercana a Copenhague),
`hard_limit = 1` para que cada máquina procese una contribución a la vez —lo
que de paso evita que dos visitantes simultáneos editen la misma imagen— y
`auto_stop_machines = "suspend"` para no interrumpir una generación a medias.

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
