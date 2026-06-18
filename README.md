# Brújula — Buscador de Empleos (validación)

Agregador de empleos para Perú. Consolida ofertas, las deduplica, las filtra
por relevancia y te redirige al portal original. Fase de validación.

## Requisitos

- Python 3.9+
- Una API key de Jooble (gratis en https://jooble.org/api/about)

## Instalación y uso

```bash
cd backend
pip install -r requirements.txt

# Define tu API key (NO la escribas en el código):
export JOOBLE_API_KEY="tu_key_aqui"        # Linux / Mac
# $env:JOOBLE_API_KEY="tu_key_aqui"        # Windows PowerShell

# Inicia el servidor:
uvicorn api:app --reload --port 8000
```

Abre **http://localhost:8000** en el navegador. Escribe un cargo y una ciudad,
y verás los resultados en pantalla. Cada oferta enlaza a su portal original.

## Estructura

- `backend/jobs_engine.py` — motor de búsqueda (ingesta, dedup, filtro).
- `backend/api.py` — API web FastAPI.
- `frontend/index.html` — interfaz (HTML/CSS/JS puro).
- `CLAUDE.md` — guía detallada del proyecto y próximos pasos.

## Próximos pasos

Ver `CLAUDE.md` para el detalle. En resumen: validar cobertura de Perú,
añadir el match con IA (el diferenciador), sumar más fuentes legales, y
endurecer para producción.

## Nota legal

Este proyecto agrega y redirige; no aloja ni republica ofertas. No hace
scraping de portales que lo prohíben. El acceso a fuentes como Computrabajo
o Bumeran requiere acuerdos comerciales con esas plataformas.
