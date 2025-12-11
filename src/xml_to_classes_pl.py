import xml.etree.ElementTree as ET
import re
from pathlib import Path

# ----------------------------
# PATH SETUP
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_XML = PROJECT_ROOT / 'data' / 'target_medicines.xml'
OUTPUT_PL = PROJECT_ROOT / 'kb' / 'classes.pl'

NS = {'db': 'http://www.drugbank.ca'}

# ----------------------------
# HELPERS
# ----------------------------
def normalize_atom(text: str) -> str:
    """
    Convert free text to valid Prolog atom.
    Example: 'Non-Steroidal Anti-Inflammatory Agents'
          -> non_steroidal_anti_inflammatory_agents
    """
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

# ----------------------------
# MAIN LOGIC
# ----------------------------
def xml_to_classes_pl():

    if not INPUT_XML.exists():
        raise FileNotFoundError(f"Input XML not found: {INPUT_XML}")

    OUTPUT_PL.parent.mkdir(exist_ok=True)

    tree = ET.parse(INPUT_XML)
    root = tree.getroot()

    count = 0

    with open(OUTPUT_PL, 'w', encoding='utf-8') as f:
        f.write('% Auto-generated drug class facts from target_medicines.xml\n\n')

        for drug in root.findall('db:drug', NS):
            drug_id = drug.findtext(
                "db:drugbank-id[@primary='true']",
                namespaces=NS
            )

            if not drug_id:
                continue

            # Navigate: drug -> categories -> category -> category
            for cat in drug.findall(
                'db:categories/db:category/db:category',
                NS
            ):
                if cat.text:
                    class_atom = normalize_atom(cat.text)
                    f.write(f"drug_class('{drug_id}', {class_atom}).\n")
                    count += 1

    print(f"✅ Generated {count} drug class facts in {OUTPUT_PL}")

# ----------------------------
# ENTRY POINT
# ----------------------------
if __name__ == '__main__':
    xml_to_classes_pl()
