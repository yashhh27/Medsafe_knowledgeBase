import xml.etree.ElementTree as ET
import re
from pathlib import Path

# ----------------------------
# PATH SETUP
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_XML = PROJECT_ROOT / 'data' / 'target_medicines.xml'

# Existing high-risk interaction output (UNCHANGED role)
OUTPUT_PL = PROJECT_ROOT / 'kb' / 'food_interactions.pl'

# ✅ NEW: raw food guidance preservation
OUTPUT_NOTES_PL = PROJECT_ROOT / 'kb' / 'food_notes.pl'

NS = {'db': 'http://www.drugbank.ca'}

# ----------------------------
# HELPERS
# ----------------------------
def normalize_atom(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


def map_food_effect(text: str):
    """
    Maps ONLY universally accepted, high-risk food interactions.
    """
    t = text.lower()

    if 'grapefruit' in t:
        return 'grapefruit', 'increased_drug_level'
    if 'alcohol' in t:
        return 'alcohol', 'liver_toxicity'
    if 'fat' in t or 'fatty' in t:
        return 'high_fat_meal', 'altered_absorption'
    if 'calcium' in t or 'dairy' in t or 'milk' in t:
        return 'dairy', 'reduced_absorption'
    if 'vitamin k' in t:
        return 'vitamin_k_foods', 'reduced_anticoagulant_effect'
    if 'caffeine' in t:
        return 'caffeine', 'increased_stimulation'

    return None, None


# ----------------------------
# MAIN LOGIC
# ----------------------------
def xml_to_food_interactions_pl():

    if not INPUT_XML.exists():
        raise FileNotFoundError(f"Input XML not found: {INPUT_XML}")

    OUTPUT_PL.parent.mkdir(exist_ok=True)

    tree = ET.parse(INPUT_XML)
    root = tree.getroot()

    seen_interactions = set()
    seen_notes = set()

    interaction_count = 0
    note_count = 0

    with open(OUTPUT_PL, 'w', encoding='utf-8') as f_interactions, \
         open(OUTPUT_NOTES_PL, 'w', encoding='utf-8') as f_notes:

        # Headers
        f_interactions.write(
            '% Auto-generated HIGH-RISK food–drug interaction facts\n\n'
        )
        f_notes.write(
            '% Auto-generated RAW food interaction notes (DrugBank-preserved)\n\n'
        )

        for drug in root.findall('db:drug', NS):

            drug_id = drug.findtext(
                "db:drugbank-id[@primary='true']",
                namespaces=NS
            )
            if not drug_id:
                continue

            food_section = drug.find('db:food-interactions', NS)
            if food_section is None:
                continue

            for fi in food_section.findall('db:food-interaction', NS):
                if not fi.text:
                    continue

                # ----------------------------
                # ✅ 1️⃣ Preserve RAW DrugBank text (NEW)
                # ----------------------------
                raw_text = fi.text.strip().replace("'", "")

                note_key = (drug_id, raw_text)
                if note_key not in seen_notes:
                    seen_notes.add(note_key)
                    f_notes.write(
                        f"food_note('{drug_id}', '{raw_text}').\n"
                    )
                    note_count += 1

                # ----------------------------
                # ✅ 2️⃣ Infer ONLY high-risk interactions (UNCHANGED LOGIC)
                # ----------------------------
                food, effect = map_food_effect(raw_text)
                if not food:
                    continue

                interaction_key = (drug_id, food, effect)
                if interaction_key in seen_interactions:
                    continue

                seen_interactions.add(interaction_key)
                f_interactions.write(
                    f"food_interaction('{drug_id}', {food}, {effect}).\n"
                )
                interaction_count += 1

    print(
        f"✅ Generated {interaction_count} high-risk food interactions "
        f"and {note_count} raw food notes."
    )


# ----------------------------
# ENTRY POINT
# ----------------------------
if __name__ == '__main__':
    xml_to_food_interactions_pl()
