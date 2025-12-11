import os
import xml.etree.ElementTree as ET
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE_PATH = PROJECT_ROOT / 'data' / 'full database.xml'
OUTPUT_FILE_PATH  = PROJECT_ROOT / 'data' / 'target_medicines.xml'


# Target Drugs (IDs are safest)
TARGET_DRUGS = {
    # --- Anticoagulants / Antiplatelets (CV risk) ---
    'DB00001',  # Lepirudin
    'DB00315',  # Clopidogrel
    'DB00945',  # Aspirin
    'DB00682',  # Warfarin
    'DB01225',  # Enoxaparin

    # --- Diabetes ---
    'DB00030',  # Insulin Human
    'DB00331',  # Metformin
    'DB01067',  # Glipizide
    'DB01261',  # Sitagliptin

    # --- Hypertension / CV ---
    'DB00381',  # Amlodipine
    'DB00722',  # Lisinopril
    'DB00678',  # Losartan
    'DB00999',  # Hydrochlorothiazide
    'DB00264',  # Metoprolol
    'DB01076',  # Atorvastatin
    'DB00727',  # Nitroglycerin

    # --- Asthma / Respiratory ---
    'DB01001',  # Albuterol
    'DB01222',  # Budesonide
    'DB13867',  # Fluticasone
    'DB00938',  # Salmeterol
    'DB00471',  # Montelukast

    # --- Pain / OTC / Inflammation ---
    'DB00316',  # Acetaminophen
    'DB01050',  # Ibuprofen
    'DB00788',  # Naproxen
    'DB00586',  # Diclofenac

    # --- GI / Acid ---
    'DB00338',  # Omeprazole

    # --- CNS / Renal-sensitive ---
    'DB00996',  # Gabapentin
    'DB00390',  # Digoxin
    'DB00437',  # Allopurinol

    # --- Hepatic / Pregnancy high-risk ---
    'DB00951',  # Isoniazid
    'DB00563',  # Methotrexate
    'DB00982',  # Isotretinoin

    # --- Cold / Decongestant (OTC risk) ---
    'DB00852',  # Pseudoephedrine
}


# Namespace configuration (Critical for valid output)
NS_URL = 'http://www.drugbank.ca'
ET.register_namespace('', NS_URL) # Set default namespace
ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')

def extract_xml_subset():
    absolute_input = os.path.abspath(INPUT_FILE_PATH)
    
    if not os.path.exists(absolute_input):
        print(f"Error: {absolute_input} not found.")
        return

    print(f"Reading from: {absolute_input}")
    print(f"Extracting {len(TARGET_DRUGS)} drugs to {OUTPUT_FILE_PATH}...")

    # 1. Start the Output File with the correct DrugBank Header
    # We write manually to ensure the root tag is perfect
    with open(OUTPUT_FILE_PATH, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b'<drugbank xmlns="http://www.drugbank.ca" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.drugbank.ca http://www.drugbank.ca/docs/drugbank.xsd" version="5.1" exported-on="2025-01-02">\n')

        try:
            # 2. Stream the Input File
            context = ET.iterparse(absolute_input, events=('end',))
            
            count = 0
            collected_ids = set()

            for event, elem in context:
                # Check for the Record Tag (using local name to be safe)
                if event == 'end' and elem.tag == f'{{{NS_URL}}}drug':
                    
                    # Check IDs
                    found_match = False
                    for id_tag in elem.findall(f'{{{NS_URL}}}drugbank-id'):
                        if id_tag.text in TARGET_DRUGS:
                            found_match = True
                            match_id = id_tag.text
                            break
                    
                    # If match found and not duplicate
                    if found_match and match_id not in collected_ids:
                        
                        # [CRITICAL] Check if it's a "skeleton" record (no interactions/classes)
                        # We peek at child tags to see if it has data
                        has_data = elem.find(f'{{{NS_URL}}}drug-interactions') is not None or \
                                   elem.find(f'{{{NS_URL}}}mechanism-of-action') is not None or \
                                   elem.find(f'{{{NS_URL}}}food-interactions') is not None 
                        
                        if has_data:
                            print(f"✅ Extracting: {match_id}")
                            
                            # Serialize this specific element tree to string
                            # and write it immediately to our output file
                            xml_str = ET.tostring(elem, encoding='utf-8')
                            f.write(xml_str)
                            f.write(b'\n') # Newline for readability
                            
                            collected_ids.add(match_id)
                            count += 1
                        else:
                            print(f"⚠️  Skipping skeleton record for {match_id}")

                    # Clear memory
                    elem.clear()

        except Exception as e:
            print(f"Error: {e}")

        # 3. Close the Root Tag
        f.write(b'</drugbank>')

    print(f"\nSuccess! Extracted {count} full drug records to '{OUTPUT_FILE_PATH}'.")

if __name__ == "__main__":
    extract_xml_subset()