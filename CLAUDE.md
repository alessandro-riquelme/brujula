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
│   ├── jobs_engine.py   # MOTOR: ingesta + dedup + filtro. Lógica pura, sin web.
│   ├── api.py           # FastAPI: expone /api/search y sirve el frontend.
│   └── requirements.txt
├── frontend/
│   └── index.html       # HTML/CSS/JS puro. Muestra resultados en pantalla.
├── README.md            # Cómo correrlo.
└── CLAUDE.md            # Este archivo.
```

El flujo: `frontend` → `GET /api/search` → `api.py` → `jobs_engine.search_jobs()`
→ Jooble → dedup → filtro → JSON de vuelta → tarjetas en pantalla.

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
- Deduplicación por título+empresa+ubicación (fusiona la misma vacante de
  varias fuentes y conserva todos los links).
- Filtro de relevancia por palabras clave + sinónimos bilingües ES/EN.
- Fix de "Lima, Ohio": se fuerza ", Peru" en la ubicación.
- Frontend que muestra resultados en pantalla y redirige al origen.
- Aviso automático si muchas ofertas parecen no ser de Perú.

## Lo que FALTA (en orden de prioridad)

### 1. [VALIDAR-COBERTURA] — hacer ANTES de invertir más
Medir empíricamente cuántas ofertas **peruanas relevantes** devuelve Jooble.
En pruebas, Jooble resolvió "Lima" como Lima, Ohio. Hay duda real sobre si
una sola fuente alcanza. Corre ~5 búsquedas reales del nicho objetivo y
cuenta los relevantes. Si son muy pocos, la prioridad pasa a sumar fuentes.

### 2. [AI-MATCH] — el diferenciador real del producto
Reemplazar `filter_relevant()` (hoy palabras clave, frágil) por **match
semántico**. El usuario daría su CV o una descripción, y un LLM/embeddings
puntuarían la afinidad real de cada oferta. Buscar el marcador `[AI-MATCH]`
en `jobs_engine.py` y `frontend/index.html` (ya hay huecos preparados).
Salida esperada por oferta: `relevance` (0..1) y `why` (explicación corta).

### 3. [ADD-SOURCE] — más fuentes legales
Añadir Careerjet y/o APIs de ATS (Greenhouse, Lever, Workable) como
funciones `fetch_<fuente>()` con la misma forma de salida que
`fetch_jooble()`. Unirlas en `search_jobs()` antes de `dedupe()`.
Computrabajo/Bumeran tienen APIs pero CERRADAS (requieren acuerdo
comercial); no intentar scraping.

### 4. [PROD-HARDENING] — antes de exponer al público
- Confirmar con Jooble que el plan permite **uso comercial** (hoy free tier
  = probablemente solo pruebas).
- Caché de resultados por (query, ciudad) para no quemar la única API key.
- Rate limiting por IP.
- Restringir CORS (hoy abierto a todos).
- Registrar búsquedas para aprendizaje (qué busca la gente).
- Política de privacidad (más aún si se guardan CVs para el match).

## Reglas que NO romper

- **Nunca** hardcodear la API key. Solo variable de entorno.
- **Nunca** scraping de Computrabajo/Indeed/Bumeran/LinkedIn — el modelo es
  por API/acuerdo y redirección. Es una decisión legal, no técnica.
- Mantener `jobs_engine.py` sin dependencias web (testeable aislado).
- Mantener la redirección al portal original intacta (es lo que hace legal
  al agregador).
