"""
================================================================
  API WEB — FastAPI
================================================================
Expone el motor de búsqueda (jobs_engine.py) como un endpoint HTTP
que el frontend consume. También sirve los archivos estáticos del
frontend para que todo corra desde un solo proceso en desarrollo.

----------------------------------------------------------------
NOTAS PARA CLAUDE CODE:
----------------------------------------------------------------
1. [API KEY] La key de Jooble se lee SOLO de la variable de
   entorno JOOBLE_API_KEY. Nunca la pongas en el código.
   En desarrollo:  export JOOBLE_API_KEY="..."  (Linux/Mac)
                   $env:JOOBLE_API_KEY="..."     (PowerShell)

2. [RATE LIMITS / COMERCIAL] En una web pública TODOS los
   usuarios consumen la MISMA key. Antes de exponer al público
   hay que: (a) confirmar con Jooble que el plan permite uso
   comercial, y (b) añadir caché y rate limiting. Ver TODO
   [PROD-HARDENING] más abajo.

3. [CORS] Hoy permite todos los orígenes para facilitar el
   desarrollo local. RESTRINGIR antes de producción.

4. [ENDPOINTS]
   GET /api/search?q=<query>&city=<ciudad>  -> JSON con resultados
   GET /                                     -> sirve el frontend
================================================================
"""

import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import jobs_engine

app = FastAPI(title="Buscador de Empleos — API de validación")

# [CORS] Abierto para desarrollo. RESTRINGIR en producción.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=2, description="Cargo o palabras clave"),
    city: str = Query("Lima", description="Ciudad (se fuerza Perú)"),
    filter: bool = Query(True, description="Aplicar filtro de relevancia"),
):
    """
    Endpoint principal. El frontend llama aquí y recibe los empleos
    ya consolidados, deduplicados y filtrados.
    """
    api_key = os.environ.get("JOOBLE_API_KEY")
    if not api_key:
        # [API KEY] Mensaje claro si falta la variable de entorno.
        raise HTTPException(
            status_code=500,
            detail="Falta JOOBLE_API_KEY. Define la variable de entorno antes de iniciar.",
        )

    careerjet_affid = os.environ.get("CAREERJET_AFFID")  # opcional

    try:
        result = jobs_engine.search_jobs(
            api_key, q, city,
            apply_filter=filter,
            careerjet_affid=careerjet_affid,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # [PROD-HARDENING] TODO antes de público:
    #   - cachear resultados por (q, city) unos minutos para no quemar la key
    #   - limitar peticiones por IP (slowapi o similar)
    #   - registrar qué busca la gente (aprendizaje de validación)
    return result


# ----------------------------------------------------------------------
# Servir el frontend estático (en dev, todo desde un proceso)
# ----------------------------------------------------------------------
# [DEPLOY] En producción quizá prefieras servir el frontend por
# separado (Vercel/Netlify) y dejar esta API solo como backend.
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# Monta el resto de archivos estáticos (css, js) si los separas luego.
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ----------------------------------------------------------------------
# Para correr:  uvicorn api:app --reload --port 8000
# Luego abre:   http://localhost:8000
# ----------------------------------------------------------------------
