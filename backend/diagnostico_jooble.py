#!/usr/bin/env python3
"""
DIAGNÓSTICO JOOBLE — ver qué devuelve la API en crudo
------------------------------------------------------
Corre esto para entender por qué tu prototipo muestra pocas ofertas
aunque pe.jooble.org tenga muchas. No filtra ni deduplica: te muestra
lo que la API entrega tal cual, con distintas formas de pedir Perú.

USO (en la carpeta backend, con tu key ya exportada):
    python diagnostico_jooble.py
o pasando la key directo:
    python diagnostico_jooble.py TU_API_KEY
"""

import os
import sys
import json
import requests

ENDPOINT = "https://pe.jooble.org/api/"   # FASE 1: probar subdominio peruano
CAREERJET_ENDPOINT = "http://public.api.careerjet.net/search"

JOOBLE_HOSTS_A_PROBAR = [
    ("pe.jooble.org",  "https://pe.jooble.org/api/"),
    ("us.jooble.org",  "https://us.jooble.org/api/"),
    ("jooble.org",     "https://jooble.org/api/"),
]


def probar_careerjet(affid, keywords, location, locale, label):
    """Prueba un query en la API de Careerjet y muestra las primeras ubicaciones."""
    params = {
        "keywords": keywords,
        "location": location,
        "locale_code": locale,
        "affid": affid,
        "page": 1,
        "pagesize": 20,
    }
    try:
        r = requests.get(CAREERJET_ENDPOINT, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"\n[{label}] ERROR: {e}")
        return

    total = data.get("hits", 0)
    jobs = data.get("jobs", [])
    print(f"\n{'='*60}")
    print(f"  PRUEBA CAREERJET: {label}")
    print(f"  keywords='{keywords}'  location='{location}'  locale='{locale}'")
    print(f"{'='*60}")
    print(f"  hits (total): {total}")
    print(f"  Ofertas en esta página: {len(jobs)}")
    if jobs:
        print(f"\n  Primeras 8 ubicaciones devueltas:")
        for j in jobs[:8]:
            loc = j.get("locations", "?")
            title = j.get("title", "?")[:45]
            print(f"    - [{loc}]  {title}")


def probar_host(api_key, host_label, endpoint, keywords, location):
    """Prueba un host específico de Jooble. Devuelve True si responde sin error."""
    payload = {"keywords": keywords, "location": location,
               "page": "1", "ResultOnPage": 10}
    print(f"\n  HOST: {host_label}  →  {endpoint}<KEY>")
    try:
        r = requests.post(endpoint + api_key, json=payload, timeout=20)
        if r.status_code == 403:
            print(f"  RESULTADO: 403 Forbidden — key inválida para este endpoint")
            return False
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  RESULTADO: ERROR — {e}")
        return False

    total = data.get("totalCount", 0)
    jobs  = data.get("jobs", [])
    print(f"  RESULTADO: OK  |  totalCount={total}  |  ofertas en página={len(jobs)}")
    if jobs:
        print(f"  Primeras 6 ubicaciones:")
        for j in jobs[:6]:
            print(f"    - [{j.get('location','?')}]  {j.get('title','?')[:50]}")
    return True


def probar(api_key, keywords, location, label):
    """Hace una llamada y reporta cuántas ofertas y de dónde son."""
    payload = {"keywords": keywords, "location": location,
               "page": "1", "ResultOnPage": 20}
    try:
        r = requests.post(ENDPOINT + api_key, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"\n[{label}] ERROR: {e}")
        return

    total = data.get("totalCount", 0)
    jobs = data.get("jobs", [])
    print(f"\n{'='*60}")
    print(f"  PRUEBA: {label}")
    print(f"  keywords='{keywords}'  location='{location}'")
    print(f"{'='*60}")
    print(f"  totalCount que reporta Jooble: {total}")
    print(f"  Ofertas en esta página: {len(jobs)}")
    if jobs:
        print(f"\n  Primeras 8 ubicaciones devueltas:")
        for j in jobs[:8]:
            loc = j.get("location", "?")
            title = j.get("title", "?")[:45]
            print(f"    - [{loc}]  {title}")


def main():
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("JOOBLE_API_KEY")
    careerjet_affid = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("CAREERJET_AFFID")
    if not api_key:
        sys.exit("Define JOOBLE_API_KEY o pásala como argumento.")

    print("\nDIAGNÓSTICO: comparando formas de pedir empleos de Perú")
    print("Mira la columna [ubicación] — debería decir lugares de Perú,")
    print("no 'OH', 'TX' ni ciudades de EE.UU.\n")

    # ---------------------------------------------------------------
    # FASE 1 — detectar qué host de Jooble acepta esta API key
    # ---------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  FASE 1: detectando host válido para la API key")
    print(f"{'='*60}")
    hosts_ok = []
    for host_label, endpoint in JOOBLE_HOSTS_A_PROBAR:
        ok = probar_host(api_key, host_label, endpoint, "analista", "Lima, Peru")
        if ok:
            hosts_ok.append((host_label, endpoint))

    print(f"\n{'='*60}")
    if hosts_ok:
        print(f"  CONCLUSIÓN FASE 1: key funciona en → {[h for h,_ in hosts_ok]}")
    else:
        print("  CONCLUSIÓN FASE 1: TODOS los hosts devolvieron 403 o error.")
        print("  Acción requerida: contactar soporte de Jooble.")
        print("  NO se continuará con los bloques A/B.")
    print(f"{'='*60}\n")

    if not hosts_ok:
        return

    # Actualizar ENDPOINT al primer host que funcionó
    global ENDPOINT
    ENDPOINT = hosts_ok[0][1]
    print(f"  (Usando {hosts_ok[0][0]} para los bloques A/B)\n")

    # --- BLOQUE A: variantes de location con keyword fija ---
    print("\n>>> BLOQUE A: variantes de location (keyword='analista')")
    probar(api_key, "analista", "Lima",                  "A1  'Lima' (ambiguo, referencia)")
    probar(api_key, "analista", "Lima, Peru",            "A2  'Lima, Peru' (prototipo actual)")
    probar(api_key, "analista", "Lima, Perú",       "A3  'Lima, Perú' (con tilde)")
    probar(api_key, "analista", "Lima PE",               "A4  'Lima PE' (código ISO)")
    probar(api_key, "analista", "Lima Peru South America","A5  'Lima Peru South America'")
    probar(api_key, "analista", "Miraflores",            "A6  'Miraflores' (distrito conocido)")
    probar(api_key, "analista", "San Isidro",            "A7  'San Isidro' (distrito financiero)")
    probar(api_key, "analista", "Surco",                 "A8  'Surco' (distrito)")
    probar(api_key, "analista", "Peru",                  "A9  Solo 'Peru'")

    # --- BLOQUE B: keywords del nicho objetivo con mejor location del A ---
    print("\n>>> BLOQUE B: keywords del nicho (location='Lima, Peru')")
    probar(api_key, "desarrollador",  "Lima, Peru", "B1  desarrollador")
    probar(api_key, "ingeniero",      "Lima, Peru", "B2  ingeniero")
    probar(api_key, "marketing",      "Lima, Peru", "B3  marketing")
    probar(api_key, "contador",       "Lima, Peru", "B4  contador")
    probar(api_key, "analyst",        "Lima, Peru", "B5  analyst (en inglés)")
    probar(api_key, "developer",      "Lima, Peru", "B6  developer (en inglés)")
    probar(api_key, "",               "Lima, Peru", "B7  SIN keyword (volumen máximo)")

    print(f"\n{'='*60}")
    print("  RESUMEN JOOBLE:")
    print("  - ¿Alguna variante del bloque A devuelve ubicaciones peruanas?")
    print("  - ¿Algún keyword del bloque B sube el totalCount a >10?")
    print("  - Si todo da cero o EE.UU.: Jooble no cubre Perú con esta key.")
    print(f"{'='*60}\n")

    # --- BLOQUE C: Careerjet con locale peruano ---
    if not careerjet_affid:
        print("\n>>> BLOQUE C: Careerjet — SALTADO (define CAREERJET_AFFID o pásalo como 2do argumento)")
        print("    Regístrate gratis en: https://www.careerjet.com/partners/\n")
        return

    print("\n>>> BLOQUE C: Careerjet (locale=es_PE)")
    probar_careerjet(careerjet_affid, "analista",     "Lima",   "es_PE", "C1  analista / Lima / es_PE")
    probar_careerjet(careerjet_affid, "desarrollador","Lima",   "es_PE", "C2  desarrollador / Lima / es_PE")
    probar_careerjet(careerjet_affid, "ingeniero",    "Lima",   "es_PE", "C3  ingeniero / Lima / es_PE")
    probar_careerjet(careerjet_affid, "marketing",    "Lima",   "es_PE", "C4  marketing / Lima / es_PE")
    probar_careerjet(careerjet_affid, "",             "Lima",   "es_PE", "C5  SIN keyword / Lima / es_PE (volumen máximo)")
    probar_careerjet(careerjet_affid, "",             "Peru",   "es_PE", "C6  SIN keyword / Peru / es_PE")
    probar_careerjet(careerjet_affid, "analista",     "Lima",   "en_US", "C7  analista / Lima / en_US (control: qué pasa sin locale PE)")

    print(f"\n{'='*60}")
    print("  RESUMEN CAREERJET:")
    print("  - ¿El bloque C devuelve ubicaciones peruanas reales?")
    print("  - Compara C5 vs C7: el locale es_PE debería marcar la diferencia.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
