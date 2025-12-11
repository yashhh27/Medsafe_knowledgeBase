import xml.etree.ElementTree as ET
import re
from pathlib import Path

# ----------------------------
# PATH SETUP
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_XML = PROJECT_ROOT / 'data' / 'target_medicines.xml'
OUTPUT_PL = PROJECT_ROOT / 'kb' / 'interactions.pl'

NS = {'db': 'http://www.drugbank.ca'}

# ----------------------------
# HELPERS
# ----------------------------
def normalize_atom(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


def map_interaction_effect(description: str) -> str:
    """
    Map free-text DrugBank interaction descriptions
    to controlled Prolog atoms.
    """
    d = description.lower()

    if 'bleeding' in d:
        return 'bleeding_risk'

    if 'anticoagulant' in d:
        return 'increased_anticoagulant_effect'

    if 'qt' in d or 'arrhythmia' in d:
        return 'cardiac_risk'

    if 'serotonin syndrome' in d:
        return 'serotonin_syndrome'

    if 'cyp' in d and ('inhibit' in d or 'inhibitor' in d):
        return 'enzyme_inhibition'

    if 'cyp' in d and ('induce' in d or 'inducer' in d):
        return 'enzyme_induction'

    if 'hypotension' in d or 'blood pressure' in d:
        return 'hypotension_risk'

    if 'sedation' in d or 'cns depression' in d:
        return 'cns_depression'

    if 'increase' in d:
        return 'increased_effect'

    if 'decrease' in d or 'reduced' in d:
        return 'reduced_effect'

    return 'interaction'


# ----------------------------
# MAIN LOGIC
# ----------------------------
def xml_to_interactions_pl():

    if not INPUT_XML.exists():
        raise FileNotFoundError(f"Input XML not found: {INPUT_XML}")

    OUTPUT_PL.parent.mkdir(exist_ok=True)

    tree = ET.parse(INPUT_XML)
    root = tree.getroot()

    seen_pairs = set()
    count = 0

    with open(OUTPUT_PL, 'w', encoding='utf-8') as f:
        f.write('% Auto-generated drug interaction facts\n\n')

        for drug in root.findall('db:drug', NS):
            primary_id = drug.findtext(
                "db:drugbank-id[@primary='true']",
                namespaces=NS
            )

            if not primary_id:
                continue

            for interaction in drug.findall(
                'db:drug-interactions/db:drug-interaction',
                NS
            ):
                other_id = interaction.findtext(
                    'db:drugbank-id',
                    namespaces=NS
                )
                description = interaction.findtext(
                    'db:description',
                    namespaces=NS
                )

                if not other_id or not description:
                    continue

                # Canonical ordering (VERY IMPORTANT)
                a, b = sorted([primary_id, other_id])
                key = (a, b)

                if key in seen_pairs:
                    continue

                seen_pairs.add(key)

                effect = map_interaction_effect(description)

                f.write(
                    f"interaction('{a}', '{b}', {effect}).\n"
                )

                count += 1

    print(f"✅ Generated {count} unique interaction facts in {OUTPUT_PL}")


# ----------------------------
# ENTRY POINT
# ----------------------------
if __name__ == '__main__':
    xml_to_interactions_pl()
