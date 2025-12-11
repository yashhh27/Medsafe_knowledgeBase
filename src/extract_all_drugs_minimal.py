import os
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE_PATH = PROJECT_ROOT / 'data' / 'full database.xml'
OUTPUT_FILE_PATH = PROJECT_ROOT / 'data' / 'all_drugs_minimal.xml'

NS = {'db': 'http://www.drugbank.ca'}
NS_URL = NS['db']

ET.register_namespace('', NS_URL)
ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')


def extract_all_drugs_minimal():
    absolute_input = os.path.abspath(INPUT_FILE_PATH)

    if not os.path.exists(absolute_input):
        raise FileNotFoundError(absolute_input)

    with open(OUTPUT_FILE_PATH, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            b'<drugbank xmlns="http://www.drugbank.ca">\n'
        )

        context = ET.iterparse(absolute_input, events=('end',))
        count = 0

        for event, elem in context:
            if elem.tag == f'{{{NS_URL}}}drug':

                drug_id_el = elem.find(
                    "db:drugbank-id[@primary='true']",
                    NS
                )
                name_el = elem.find("db:name", NS)

                if drug_id_el is None or name_el is None:
                    elem.clear()
                    continue

                # Create NEW trimmed drug element
                drug = ET.Element(f'{{{NS_URL}}}drug')

                ET.SubElement(drug, f'{{{NS_URL}}}drugbank-id').text = drug_id_el.text
                ET.SubElement(drug, f'{{{NS_URL}}}name').text = name_el.text

                # Indication
                indication = elem.find("db:indication", NS)
                if indication is not None:
                    ET.SubElement(drug, f'{{{NS_URL}}}indication').text = indication.text

                # Drug interactions
                drug_interactions = elem.find("db:drug-interactions", NS)
                if drug_interactions is not None:
                    drug.append(drug_interactions)

                # Food interactions
                food_interactions = elem.find("db:food-interactions", NS)
                if food_interactions is not None:
                    drug.append(food_interactions)

                f.write(ET.tostring(drug, encoding='utf-8'))
                f.write(b'\n')

                count += 1
                elem.clear()

        f.write(b'</drugbank>')
        print(f"✅ Extracted {count} drugs to {OUTPUT_FILE_PATH}")


if __name__ == "__main__":
    extract_all_drugs_minimal()
