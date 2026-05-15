"""
Scraper du site ADEME (Agence de la transition écologique)

Utilise l'API interne de agirpourlatransition.ademe.fr pour récupérer
les actualités et événements. L'API a été découverte en interceptant
les requêtes XHR faites par le navigateur avec Scrapling DynamicFetcher.

API endpoint : https://cdr-generique-agir.ademe.fr/api/v1/search-resource
Méthode      : POST (JSON)
"""

import json
import re
from datetime import datetime
from scrapling.fetchers import Fetcher

# --- Configuration ---
API_URL = "https://cdr-generique-agir.ademe.fr/api/v1/search-resource"
API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://agirpourlatransition.ademe.fr",
    "Referer": "https://agirpourlatransition.ademe.fr/",
}

# Collections disponibles (découvertes via DynamicFetcher)
COLLECTIONS = {
    "BREVES": "Actualités",
    "EVENTS2024": "Événements",
}

# Codes cible (audiences) — découverts en interceptant les requêtes XHR
CIBLES = {
    "CIBLEENTREPRISES": "Entreprises",
    "CIBLECOLLECTIVIT": "Collectivités",
}

fetcher = Fetcher(impersonate="chrome124", stealthy_headers=True)


def strip_html(html_text: str) -> str:
    """Supprime les balises HTML d'un texte."""
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_resources(
    collection: str,
    cible: str | None = None,
    page: int = 1,
    nb_results: int = 20,
) -> dict:
    """Interroge l'API ADEME et retourne les ressources brutes."""
    payload: dict = {
        "parameters": {
            "collection": [collection],
            "page": page,
            "nbresultats": nb_results,
            "filtres": {},
        }
    }
    if cible:
        payload["parameters"]["filtres"]["cible"] = [cible]

    response = fetcher.post(API_URL, json=payload, headers=API_HEADERS)

    if response.status != 200:
        print(f"  [ERREUR] HTTP {response.status} pour collection={collection}, cible={cible}")
        return {}

    try:
        return response.json()
    except Exception as e:
        print(f"  [ERREUR] JSON : {e}")
        return {}


def format_resource(item: dict, category: str) -> dict:
    """Normalise un item de l'API en dictionnaire lisible."""
    description_html = item.get("description", "")
    description_text = strip_html(description_html)

    return {
        "id": item.get("id"),
        "titre": item.get("title", "").strip(),
        "categorie": category,
        "date": item.get("dateOrdoPublication", ""),
        "description": description_text[:600] + ("…" if len(description_text) > 600 else ""),
        "mots_cles": item.get("keywords") or [],
        "zone_geo": item.get("zoneGeo") or [],
    }


def scrape(
    collection_code: str,
    cible_code: str | None = None,
    nb_results: int = 20,
    verbose: bool = True,
) -> list[dict]:
    """Scrape une collection (avec filtre audience optionnel)."""
    collection_label = COLLECTIONS.get(collection_code, collection_code)
    cible_label = CIBLES.get(cible_code, cible_code) if cible_code else "Toutes audiences"
    label = f"{collection_label} – {cible_label}"

    if verbose:
        print(f"\n[{label}] Requête API...")

    data = fetch_resources(collection_code, cible=cible_code, nb_results=nb_results)
    if not data:
        return []

    total = data.get("totalResources", 0)
    resources = data.get("resources", [])

    if verbose:
        print(f"  → {total} ressources totales, {len(resources)} récupérées")

    return [format_resource(r, label) for r in resources]


def main():
    print("=" * 65)
    print("Scraper ADEME — agirpourlatransition.ademe.fr")
    print(f"Démarré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    print("=" * 65)

    all_results: dict[str, list[dict]] = {}

    # 1. Actualités par audience
    for cible_code, label in CIBLES.items():
        key = f"actualites_{label.lower()}"
        all_results[key] = scrape("BREVES", cible_code=cible_code, nb_results=20)

    # 2. Tous les événements à venir
    all_results["evenements"] = scrape("EVENTS2024", nb_results=14)

    # 3. Affichage du résumé
    print("\n" + "=" * 65)
    print("RÉSUMÉ")
    print("=" * 65)
    total_count = 0
    for category, items in all_results.items():
        print(f"\n  {category} : {len(items)} élément(s)")
        for item in items[:3]:
            print(f"    • [{item['date']:20s}] {item['titre'][:55]}")
        total_count += len(items)

    # 4. Export JSON
    output = {
        "source": "ADEME – agirpourlatransition.ademe.fr",
        "api_endpoint": API_URL,
        "date_extraction": datetime.now().isoformat(),
        "total": total_count,
        "donnees": all_results,
    }
    output_file = "ademe_donnees.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ {total_count} éléments exportés dans '{output_file}'")


if __name__ == "__main__":
    main()
