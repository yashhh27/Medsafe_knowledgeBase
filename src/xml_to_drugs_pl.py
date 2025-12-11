import xml.etree.ElementTree as ET
import re
import os
from pathlib import Path
# ----------------------------
# CONFIG
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_XML = PROJECT_ROOT / 'data' / 'target_medicines.xml'
OUTPUT_PL = PROJECT_ROOT / 'kb' / 'drugs.pl'
NS = {'db': 'http://www.drugbank.ca'}

# ----------------------------
# HELPERS
# ----------------------------
def normalize_name(name: str) -> str:
    """
    Convert drug name into a valid Prolog atom.
    Example: 'Human Insulin' -> human_insulin
    """
    name = name.lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    return name.strip('_')

# ----------------------------
# MAIN LOGIC
# ----------------------------
def xml_to_drugs_pl():
    if not os.path.exists(INPUT_XML):
        raise FileNotFoundError(f"Input XML not found: {INPUT_XML}")

    os.makedirs(os.path.dirname(OUTPUT_PL), exist_ok=True)

    tree = ET.parse(INPUT_XML)
    root = tree.getroot()

    count = 0

    with open(OUTPUT_PL, 'w', encoding='utf-8') as f:
        f.write('% Auto-generated from target_medicines.xml\n\n')

        for drug in root.findall('db:drug', NS):
            drug_id = drug.findtext(
                "db:drugbank-id[@primary='true']", 
                namespaces=NS
            )
            name = drug.findtext('db:name', namespaces=NS)

            if not drug_id or not name:
                continue

            prolog_name = normalize_name(name)
            f.write(f"drug('{drug_id}', {prolog_name}).\n")
            count += 1

    print(f"✅ Generated {count} drug facts in {OUTPUT_PL}")

# ----------------------------
# ENTRY POINT
# ----------------------------
if __name__ == '__main__':
    xml_to_drugs_pl()
