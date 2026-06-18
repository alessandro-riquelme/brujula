"""
================================================================
  MOTOR DE BÚSQUEDA DE EMPLEOS
================================================================
Este módulo es el CORAZÓN del producto. Contiene la lógica ya
validada en la versión CLI: ingesta desde Jooble, deduplicación
y filtro de relevancia.

NO contiene nada de web — solo lógica pura. Eso permite testearlo
de forma aislada y reutilizarlo desde la API (api.py) o desde un
script de línea de comandos.

----------------------------------------------------------------
NOTAS PARA CLAUDE CODE (lee esto antes de modificar):
----------------------------------------------------------------
1. [FUENTE ÚNICA] Hoy solo consulta Jooble. Para añadir fuentes
   (Careerjet, ATS como Greenhouse/Lever), crea funciones
   `fetch_<fuente>()` con la MISMA forma de salida que
   `fetch_jooble()` (lista de dicts con las mismas claves) y
   únelas antes de `dedupe()`. Ver TODO marcado [ADD-SOURCE].

2. [MATCH POR IA - PENDIENTE] El diferenciador real del producto
   (match semántico con IA) NO está implementado. Hoy el filtro
   es por palabras clave + sinónimos bilingües, que es frágil.
   Ver TODO marcado [AI-MATCH] en filter_relevant().

3. [COBERTURA PERÚ - SIN VALIDAR] Existe duda real sobre cuánta
   data peruana entrega Jooble (en pruebas resolvió "Lima" como
   Lima, Ohio). Por eso forzamos ", Peru" en la ubicación. Hay
   que medir empíricamente cuántas ofertas relevantes peruanas
   devuelve. Ver normalize_location().

4. [API KEY] Nunca hardcodear la key. Se lee de variable de
   entorno JOOBLE_API_KEY. Ver api.py.
================================================================
"""

import re
import requests

JOOBLE_HOST = "pe.jooble.org"          # subdominio por país; cambiar si se usa otra key
JOOBLE_ENDPOINT = f"https://{JOOBLE_HOST}/api/"
CAREERJET_ENDPOINT = "http://public.api.careerjet.net/search"


# ----------------------------------------------------------------------
# 1. INGESTA
# ----------------------------------------------------------------------
def fetch_jooble(api_key, keywords, location, pages=2, results_on_page=20):
    """
    Consulta la API de Jooble y devuelve (lista_de_jobs, total_count).

    Cada job es un dict con claves crudas de Jooble:
    title, company, location, salary, snippet, source, link, updated, type.

    [ADD-SOURCE] Para añadir otra fuente, replica esta firma:
        def fetch_careerjet(...) -> (list[dict], int)
    devolviendo dicts con LAS MISMAS claves de arriba, para que
    dedupe() y el resto funcionen sin cambios.
    """
    all_jobs = []
    total = 0
    for page in range(1, pages + 1):
        payload = {
            "keywords": keywords,
            "location": location,
            "page": str(page),
            "ResultOnPage": results_on_page,
        }
        try:
            r = requests.post(JOOBLE_ENDPOINT + api_key, json=payload, timeout=20)
            r.raise_for_status()
        except requests.HTTPError:
            raise RuntimeError(f"Jooble respondió {r.status_code}. Revisa la API key.")
        except requests.RequestException as e:
            raise RuntimeError(f"Error de conexión con Jooble: {e}")

        data = r.json()
        total = data.get("totalCount", 0)
        jobs = data.get("jobs", [])
        if not jobs:
            break
        all_jobs.extend(jobs)
    return all_jobs, total


def fetch_careerjet(affid, keywords, location, pages=2, results_on_page=20):
    """
    Consulta la API pública de Careerjet y devuelve (lista_de_jobs, total_count).

    Usa locale_code=es_PE para forzar el índice peruano de Careerjet.
    Normaliza la salida al mismo shape que fetch_jooble() para que
    dedupe() y filter_relevant() funcionen sin cambios.

    [ADD-SOURCE] Requiere CAREERJET_AFFID en el entorno. Registro
    gratuito en careerjet.com/partners/
    """
    all_jobs = []
    total = 0
    for page in range(1, pages + 1):
        params = {
            "keywords": keywords,
            "location": location,
            "locale_code": "es_PE",
            "affid": affid,
            "page": page,
            "pagesize": results_on_page,
        }
        try:
            r = requests.get(CAREERJET_ENDPOINT, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except requests.HTTPError:
            raise RuntimeError(f"Careerjet respondió {r.status_code}.")
        except requests.RequestException as e:
            raise RuntimeError(f"Error de conexión con Careerjet: {e}")

        if page == 1:
            total = data.get("hits", 0)
        jobs_raw = data.get("jobs", [])
        if not jobs_raw:
            break

        for j in jobs_raw:
            all_jobs.append({
                "title":    j.get("title", ""),
                "company":  j.get("company", ""),
                "location": j.get("locations", ""),
                "salary":   j.get("salary", ""),
                "snippet":  j.get("description", ""),
                "source":   j.get("site", "Careerjet"),
                "link":     j.get("url", ""),
                "updated":  j.get("date", ""),
                "type":     "",
            })
    return all_jobs, total


def normalize_location(city):
    """
    [COBERTURA PERÚ] Fuerza el país para evitar el bug de Lima, Ohio.
    Jooble no tiene parámetro de país: hay que decirlo en 'location'.
    Si el usuario ya escribió 'Peru'/'Perú', se respeta tal cual.
    """
    if not city:
        return "Lima, Peru"
    low = city.lower()
    if "peru" in low or "perú" in low:
        return city
    return f"{city}, Peru"


# ----------------------------------------------------------------------
# 2. DEDUPLICACIÓN
# ----------------------------------------------------------------------
def _normalize(text):
    if not text:
        return ""
    text = text.lower()
    for a, b in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}.items():
        text = text.replace(a, b)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean(text):
    """Quita HTML y espacios sobrantes."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def dedupe(jobs):
    """
    Agrupa la misma vacante publicada en varias fuentes.
    Clave = titulo + empresa + ubicacion (todo normalizado).
    Devuelve lista de dicts limpios con 'sources' y 'links' agregados.
    """
    groups = {}
    for job in jobs:
        key = (
            _normalize(job.get("title", "")),
            _normalize(job.get("company", "")),
            _normalize(job.get("location", "")),
        )
        if key not in groups:
            groups[key] = {
                "title": _clean(job.get("title", "")) or "Sin título",
                "company": _clean(job.get("company", "")) or "No especificada",
                "location": _clean(job.get("location", "")),
                "salary": _clean(job.get("salary", "")) or "No especificado",
                "type": _clean(job.get("type", "")),
                "snippet": _clean(job.get("snippet", "")),
                "updated": (job.get("updated", "") or "")[:10],
                "sources": [],
                "links": [],
                "relevance": 0,
            }
        src = _clean(job.get("source", "")) or "Jooble"
        if src not in groups[key]["sources"]:
            groups[key]["sources"].append(src)
        link = job.get("link", "")
        if link:
            groups[key]["links"].append(link)
    return list(groups.values())


# ----------------------------------------------------------------------
# 3. FILTRO DE RELEVANCIA
# ----------------------------------------------------------------------
_STOPWORDS = {"de", "en", "el", "la", "los", "las", "para", "con", "y",
              "o", "del", "un", "una", "por", "a", "al"}

# [AI-MATCH] Este diccionario bilingüe es un PARCHE provisional.
# El plan real es reemplazar todo filter_relevant() por un match
# semántico con IA (embeddings o un LLM que puntúe afinidad contra
# el CV/descripción del usuario). Esto solo cubre términos que
# anticipamos a mano y se rompe con sinónimos no listados
# (ej. "ML Engineer", "experto en machine learning").
_SYNONYMS = {
    "cientifico": ["scientist", "science"],
    "datos": ["data"],
    "analista": ["analyst"],
    "desarrollador": ["developer", "dev"],
    "ingeniero": ["engineer"],
    "disenador": ["designer", "design"],
    "gerente": ["manager"],
    "ventas": ["sales"],
    "contador": ["accountant", "accounting"],
    "programador": ["programmer", "developer"],
    "administrador": ["administrator", "admin"],
    "enfermero": ["nurse", "nursing"],
    "abogado": ["lawyer", "legal"],
    "docente": ["teacher", "professor"],
}


def _expand_terms(terms):
    expanded = set(terms)
    for t in terms:
        for syn in _SYNONYMS.get(t, []):
            expanded.add(syn)
    return expanded


def filter_relevant(jobs, query, min_hits=1):
    """
    Conserva ofertas cuyo TÍTULO contenga al menos `min_hits` palabras
    de la búsqueda (o sus equivalentes en inglés). Ordena por relevancia.

    [AI-MATCH] PUNTO CLAVE PARA EL FUTURO: reemplazar esta función
    por scoring semántico. Firma sugerida para no romper api.py:
        def score_relevance(jobs, user_profile) -> jobs ordenados con
        cada job['relevance'] = float 0..1 y job['why'] = explicación.
    Mantener la salida ordenada por relevancia desc.
    """
    base = [t for t in _normalize(query).split() if t not in _STOPWORDS and len(t) > 2]
    if not base:
        return jobs
    terms = _expand_terms(base)
    kept = []
    for job in jobs:
        title_norm = _normalize(job["title"])
        hits = sum(1 for t in terms if t in title_norm)
        if hits >= min_hits:
            job["relevance"] = hits
            kept.append(job)
    kept.sort(key=lambda j: j.get("relevance", 0), reverse=True)
    return kept


# ----------------------------------------------------------------------
# 4. ORQUESTADOR — lo que la API llama
# ----------------------------------------------------------------------
def search_jobs(api_key, query, city, apply_filter=True, careerjet_affid=None):
    """
    Flujo completo: ingesta -> dedup -> filtro.
    Devuelve un dict con resultados y metadatos (para mostrar en la web).

    [ADD-SOURCE] careerjet_affid es opcional: si se pasa, mezcla ambas
    fuentes antes de dedupe(). Para añadir más fuentes, replicar el mismo
    patrón: fetch_<fuente>() y sumar la lista aquí.
    """
    location = normalize_location(city)
    raw, total_jooble = fetch_jooble(api_key, query, location)

    total_careerjet = 0
    if careerjet_affid:
        try:
            cj_jobs, total_careerjet = fetch_careerjet(careerjet_affid, query, location)
            raw.extend(cj_jobs)
        except RuntimeError:
            pass  # Careerjet falla silenciosamente; Jooble sigue funcionando

    total = total_jooble + total_careerjet

    unique = dedupe(raw)
    results = filter_relevant(unique, query) if apply_filter else unique

    # Detección de ofertas que parecen NO ser de Perú (señal de cobertura)
    non_pe_hints = (", oh", ", tx", ", ny", ", ca", ", ohio", "united states", "usa")
    non_pe = sum(1 for j in unique
                 if any(h in j["location"].lower() for h in non_pe_hints))

    return {
        "query": query,
        "location": location,
        "total_jooble": total_jooble,
        "total_careerjet": total_careerjet,
        "fetched": len(raw),
        "unique": len(unique),
        "relevant": len(results),
        "non_peru_warning": non_pe > len(unique) / 2 if unique else False,
        "jobs": results,
    }
