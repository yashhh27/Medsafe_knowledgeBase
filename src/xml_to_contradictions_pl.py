import xml.etree.ElementTree as ET
import re
from pathlib import Path

# ----------------------------
# PATH SETUP
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_XML = PROJECT_ROOT / 'data' / 'target_medicines.xml'
OUTPUT_PL = PROJECT_ROOT / 'kb' / 'contraindications.pl'

NS = {'db': 'http://www.drugbank.ca'}

# ----------------------------
# CONTRAINDICATION MAP
# ----------------------------
CONTRAINDICATION_KEYWORDS = {
    'renal_impairment': ['renal', 'kidney'],
    'hepatic_impairment': ['hepatic', 'liver'],
    'pregnancy': ['pregnan'],
    'bleeding_disorder': ['bleeding', 'hemorrhage'],
    'peptic_ulcer': ['ulcer'],
    'hypertension': ['hypertension'],
    'diabetes': ['diabetes']
}

# ----------------------------
# MAIN LOGIC
# ----------------------------
def xml_to_contraindications_pl():

    if not INPUT_XML.exists():
        raise FileNotFoundError(f"Input XML not found: {INPUT_XML}")

    OUTPUT_PL.parent.mkdir(exist_ok=True)

    tree = ET.parse(INPUT_XML)
    root = tree.getroot()

    seen = set()
    count = 0

    with open(OUTPUT_PL, 'w', encoding='utf-8') as f:
        f.write('% Auto-generated contraindication facts\n\n')

        for drug in root.findall('db:drug', NS):
            drug_id = drug.findtext(
                "db:drugbank-id[@primary='true']",
                namespaces=NS
            )

            if not drug_id:
                continue

            # Collect relevant free-text fields
            text_sources = []

            for tag in ['toxicity', 'indication', 'pharmacodynamics']:
                t = drug.findtext(f'db:{tag}', namespaces=NS)
                if t:
                    text_sources.append(t.lower())

            combined_text = ' '.join(text_sources)

            for condition, keywords in CONTRAINDICATION_KEYWORDS.items():
                if any(k in combined_text for k in keywords):
                    fact = (drug_id, condition)
                    if fact not in seen:
                        seen.add(fact)
                        f.write(
                            f"contraindicated('{drug_id}', {condition}).\n"
                        )
                        count += 1

    print(f"✅ Generated {count} contraindication facts in {OUTPUT_PL}")


# ----------------------------
# ENTRY POINT
# ----------------------------
if __name__ == '__main__':
    xml_to_contraindications_pl()
