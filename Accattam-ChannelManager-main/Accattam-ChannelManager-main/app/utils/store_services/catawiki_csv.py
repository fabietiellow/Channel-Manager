"""
Libreria per la generazione di CSV bulk upload per Catawiki - Categoria Bags/Handbags.
"""

import csv
from pathlib import Path
from typing import List, Dict, Union
from datetime import datetime


# Lista completa colonne template Catawiki per Bags
CATAWIKI_BAGS_COLUMNS = [
    "Your Reference Number (optional)",
    "Your Reference Colour (optional)",
    "Auction Type (869) (optional)",
    "Object type (1879)",
    "Language",
    "Description",
    "D: Colour",
    "D: Material",
    "D: Made in (optional)",
    "D: Condition",
    "D: Height",
    "D: Width",
    "D: Era",
    "D: Number of items (optional)",
    "D: Brand",
    "D: Culture",
    "D: Century/ Timeframe",
    "D: Model Name (optional)",
    "D: Acquired from",
    "D: Year acquired",
    "D: Country acquired from",
    "D: Previous owner acquired from",
    "D: Previous owner - year acquired",
    "D: Previous owner - country acquired from",
    "D: I verify that I have obtained this object legally and that I am allowed to sell it",
    "D: Authenticity code (optional)",
    "D: Pattern (optional)",
    "D: Designer/Artist/Maker (optional)",
    "Public photo URL",
    "Estimated lot value",
    "Reserve price (optional)",
    "Start bidding from (optional)",
    "Pick up (optional)",
    "Combined shipping (optional)",
    "Shipping costs - Italy",
    "Shipping costs - Europe",
    "Shipping costs - Rest of World",
    "Country specific shipping price (optional)",
    "Shipping profile (optional)",
    "Message to Expert (optional)"
]


def item_to_catawiki_row(item: Dict) -> Dict:
    """
    Converte un dict con i dati del prodotto in un dict con le chiavi
    come in CATAWIKI_BAGS_COLUMNS.
    
    Args:
        item: dict con i dati del prodotto (da Product.to_catawiki_dict())
    
    Returns:
        dict con le colonne formattate per Catawiki
    """
    
    # Inizializza tutte le colonne a stringa vuota
    row = {col: "" for col in CATAWIKI_BAGS_COLUMNS}
    
    # ========== CAMPI OBBLIGATORI ==========
    
    # Reference e identificativi
    row["Your Reference Number (optional)"] = item.get("reference", "")
    row["Your Reference Colour (optional)"] = item.get("colour", "")
    
    # Tipo oggetto e lingua
    row["Object type (1879)"] = item.get("object_type", "Handbag")
    row["Language"] = item.get("language", "English")
    
    # Descrizione e caratteristiche principali
    row["Description"] = item.get("description", "")
    row["D: Colour"] = item.get("colour", "")
    row["D: Material"] = item.get("material", "")
    row["D: Condition"] = item.get("condition", "")
    row["D: Brand"] = item.get("brand", "")
    
    # Dimensioni (obbligatorie per bags)
    row["D: Height"] = str(item.get("height", "")) if item.get("height") else ""
    row["D: Width"] = str(item.get("width", "")) if item.get("width") else ""
    
    # Epoca e provenienza
    row["D: Era"] = item.get("era", "")
    row["D: Culture"] = item.get("culture", "")
    row["D: Century/ Timeframe"] = item.get("century_timeframe", "")
    
    # Storia di acquisizione
    row["D: Acquired from"] = item.get("acquired_from", "")
    row["D: Year acquired"] = str(item.get("year_acquired", ""))
    row["D: Country acquired from"] = item.get("country_acquired_from", "")
    
    # Previous owner
    row["D: Previous owner acquired from"] = item.get("Previous_owner_acq_from", "")
    row["D: Previous owner - year acquired"] = str(item.get("Previous_owner_year_acq", ""))
    row["D: Previous owner - country acquired from"] = item.get("Previous_owner_country_acq", "")
    
    # Verifica legale (obbligatoria)
    row["D: I verify that I have obtained this object legally and that I am allowed to sell it"] = "yes"
    
    # ========== CAMPI OPZIONALI ==========
    
    row["D: Made in (optional)"] = item.get("made_in", "")
    row["D: Number of items (optional)"] = str(item.get("number_of_items", ""))
    row["D: Model Name (optional)"] = item.get("model_name", "")
    row["D: Authenticity code (optional)"] = item.get("authenticity_code", "")
    row["D: Pattern (optional)"] = item.get("pattern", "")
    row["D: Designer/Artist/Maker (optional)"] = item.get("designer", "")
    
    # ========== FOTO ==========
    
    # Photo URLs, separati da ; (punto e virgola)
    photo_urls = item.get("photo_urls", [])
    if isinstance(photo_urls, list):
        row["Public photo URL"] = ";".join(photo_urls)
    else:
        row["Public photo URL"] = str(photo_urls)
    
    # ========== PREZZI ==========
    
    # Prezzi (solo numero, senza simbolo €)
    estimated_value = item.get("estimated_value", "")
    if estimated_value:
        row["Estimated lot value"] = str(estimated_value)
    
    row["Reserve price (optional)"] = str(item.get("reserve_price", ""))
    row["Start bidding from (optional)"] = item.get("start_bid", "1 euro")
    
    # ========== SPEDIZIONE ==========
    
    # Spedizione (solo numero)
    shipping_italy = item.get("Shipping_italy", "")
    shipping_eu = item.get("Shipping_eu", "")
    shipping_row = item.get("Shipping_row", "")
    
    row["Shipping costs - Italy"] = str(shipping_italy) if shipping_italy else ""
    row["Shipping costs - Europe"] = str(shipping_eu) if shipping_eu else ""
    row["Shipping costs - Rest of World"] = str(shipping_row) if shipping_row else ""
    
    # Opzioni spedizione
    row["Pick up (optional)"] = item.get("pick_up", "")
    row["Combined shipping (optional)"] = item.get("combined_shipping", "")
    row["Shipping profile (optional)"] = item.get("shipping_profile", "")
    
    # Messaggio all'esperto
    row["Message to Expert (optional)"] = item.get("message_to_expert", "")
    
    return row


def write_catawiki_csv(
    items: List[Dict],
    output_path: Union[str, Path],
    encoding: str = "utf-8"
) -> None:
    """
    Scrive il CSV Catawiki a partire da una lista di item.
    
    Args:
        items: lista di dict, ognuno rappresenta un prodotto
        output_path: percorso del file CSV da creare
        encoding: encoding del file (default utf-8)
    """
    output_path = Path(output_path)
    
    with output_path.open("w", newline="", encoding=encoding) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CATAWIKI_BAGS_COLUMNS)
        
        # Scrivi header
        writer.writeheader()
        
        # Scrivi righe
        for item in items:
            row = item_to_catawiki_row(item)
            writer.writerow(row)
    
    print(f"✓ CSV Catawiki scritto: {output_path.absolute()} ({len(items)} prodotti)")
    return output_path
    
    # Genera CSV di test
    write_catawiki_csv(sample_items, "test_catawiki_bags.csv")
