# CLAUDE.md — Guía para Claude Code

Este archivo te orienta (Claude Code) sobre el estado del proyecto, las
decisiones tomadas y lo que falta. Léelo antes de hacer cambios.

## Qué es esto

**Brújula** — un agregador de empleos para Perú, en fase de **validación**.
Modelo de negocio: consolidar ofertas de varias fuentes, deduplicarlas,
mostrarlas filtradas por relevancia, y **redirigir al portal original**
(no alojamos ni republicamos ofertas). Es un modelo de agregador legal,
NO scraping.

La apuesta del producto es **calidad de match sobre volumen**: pocas
ofertas pero muy afines. Esto define las prioridades de abajo.

## Arquitectura

```
buscador-empleos-web/
├── backend/
│   ├── jobs_engine.py   # MOTOR: ingesta (Jooble + Careerjet opcional) + dedup + filtro. Lógica pura, sin web.
│   ├── api.py           # FastAPI: expone /api/search y sirve el frontend.
│   └── requirements.txt
├── frontend/
│   └── index.html       # HTML/CSS/JS puro, cero build step. Ver detalle abajo.
├── README.md            # Cómo correrlo.
└── CLAUDE.md            # Este archivo.
```

El flujo: `frontend` → `GET /api/search` → `api.py` → `jobs_engine.search_jobs()`
→ Jooble (+ Careerjet si hay `CAREERJET_AFFID`) → dedup → filtro → JSON de
vuelta → tarjetas en pantalla.

### `frontend/index.html` — qué hay ahí además de las tarjetas

El frontend creció más allá de "mostrar resultados". Todo vive en un solo
archivo (sin build step), con Supabase como backend ligero para todo lo que
no es búsqueda de empleos:

- **Email gate**: antes de buscar, el usuario deja su correo (se guarda en
  `localStorage`, clave `busco_email`). No hay contraseñas.
- **Supabase** (SDK vía CDN): credenciales `SUPABASE_URL` / `SUPABASE_KEY`
  al inicio del `<script>`. La anon key es pública por diseño (protegida
  por RLS en Supabase, no es un secreto tipo `JOOBLE_API_KEY`).
  Tablas usadas: `searches` (cada búsqueda exitosa), `nps_responses`,
  `cv_uploads`, `cv_improve_clicks`.
- **NPS modal**: pensado para aparecer al hacer scroll > 120px tras la
  primera búsqueda (`localStorage` clave `busco_nps_seen` evita repetirlo).
  ⚠️ **Bug conocido**: `setupNpsScroll()` está definida pero no se llama
  desde ningún sitio (ni en `doSearch()` ni en otro lado) — el modal nunca
  se dispara hoy. Si tocas esta zona, revisa si ya se arregló.
- **Validador de CV**: el usuario sube un PDF, se lee en el navegador con
  PDF.js (no se sube el archivo a ningún servidor) y se calcula un score
  de afinidad por superposición de palabras clave (`calcScore()`). Es un
  heurístico provisional, NO el match semántico de `[AI-MATCH]`.
- **Microsoft Clarity**: analítica de sesión/heatmaps cargada sin gate de
  consentimiento. Antes de exponer más al público, revisar si el input de
  email queda enmascarado en el dashboard de Clarity (ver `[PROD-HARDENING]`
  → política de privacidad).

## Cómo correr (desarrollo)

```bash
cd backend
pip install -r requirements.txt
export JOOBLE_API_KEY="tu_key"      # PowerShell: $env:JOOBLE_API_KEY="tu_key"
uvicorn api:app --reload --port 8000
# abre http://localhost:8000
```

## Estado actual: qué FUNCIONA

- Ingesta desde Jooble (2 páginas, ~40 ofertas).
- Ingesta opcional desde Careerjet (`fetch_careerjet()`, activa solo si
  existe `CAREERJET_AFFID` en el entorno; falla en silencio si Careerjet
  cae, Jooble sigue funcionando).
- Deduplicación por título+empresa+ubicación (fusiona la misma vacante de
  varias fuentes y conserva todos los links).
- Filtro de relevancia por palabras clave + sinónimos bilingües ES/EN.
- Fix de "Lima, Ohio": se fuerza ", Peru" en la ubicación.
- Frontend que muestra resultados en pantalla y redirige al origen.
- Aviso automático si muchas ofertas parecen no ser de Perú.
- Email gate + registro de cada búsqueda en Supabase (tabla `searches`) —
  ya se está "aprendiendo qué busca la gente" (ver punto 4 de abajo).
- Validador de CV en el navegador (heurístico por palabras clave, no IA).
- Encuesta NPS (implementada pero con el bug de disparo descrito arriba).

## Lo que FALTA (en orden de prioridad)

### 0. [BUG] Arreglar el disparo del NPS
`setupNpsScroll()` en `frontend/index.html` nunca se invoca — el modal de
NPS está muerto en la práctica. Es rápido de arreglar (llamarlo tras una
búsqueda exitosa) y ya está aceptado, solo falta aplicarlo.

### 1. [VALIDAR-COBERTURA] — hacer ANTES de invertir más
Medir empíricamente cuántas ofertas **peruanas relevantes** devuelve Jooble
(+ Careerjet si está activo). En pruebas, Jooble resolvió "Lima" como Lima,
Ohio. Corre ~5 búsquedas reales del nicho objetivo y cuenta los relevantes.
Si son muy pocos, la prioridad pasa a sumar más fuentes.

### 2. [AI-MATCH] — el diferenciador real del producto
Reemplazar `filter_relevant()` (hoy palabras clave, frágil) por **match
semántico**. El validador de CV del frontend (`calcScore()`) ya cubre el
hueco a medias con superposición de palabras clave client-side, pero NO es
el match semántico con LLM/embeddings planeado. Buscar el marcador
`[AI-MATCH]` en `jobs_engine.py` y `frontend/index.html`. Salida esperada
por oferta: `relevance` (0..1) y `why` (explicación corta).

### 3. [ADD-SOURCE] — más fuentes legales
Careerjet ya está integrado (ver arriba). Falta sumar APIs de ATS
(Greenhouse, Lever, Workable) con el mismo patrón `fetch_<fuente>()`.
Computrabajo/Bumeran tienen APIs pero CERRADAS (requieren acuerdo
comercial); no intentar scraping.

### 4. [PROD-HARDENING] — antes de exponer al público
- Confirmar con Jooble que el plan permite **uso comercial** (hoy free tier
  = probablemente solo pruebas).
- Caché de resultados por (query, ciudad) para no quemar la única API key.
- Rate limiting por IP.
- Restringir CORS (hoy abierto a todos en `api.py`).
- ~~Registrar búsquedas para aprendizaje~~ — hecho vía Supabase (`searches`).
- Política de privacidad: falta explícitamente. Cubre el email del gate,
  lo que Microsoft Clarity graba de la sesión, y aclarar que los CVs se
  procesan solo en el navegador (no se suben a ningún servidor).

## Reglas que NO romper

- **Nunca** hardcodear la API key. Solo variable de entorno.
- **Nunca** scraping de Computrabajo/Indeed/Bumeran/LinkedIn — el modelo es
  por API/acuerdo y redirección. Es una decisión legal, no técnica.
- Mantener `jobs_engine.py` sin dependencias web (testeable aislado).
- Mantener la redirección al portal original intacta (es lo que hace legal
  al agregador).
