import streamlit as st
from pyswip import Prolog
from pathlib import Path
from datetime import datetime

# -------------------------------
# PROLOG SETUP
# -------------------------------
prolog = Prolog()

KB_FILES = [
    "kb/drugs.pl",
    "kb/drug_interactions.pl",   # or kb/interactions.pl in your setup
    "kb/contraindications.pl",
    "kb/food_interactions.pl",
    "kb/food_notes.pl",
    "kb/rules.pl"
]

@st.cache_resource
def load_prolog():
    p = Prolog()
    for kb in KB_FILES:
        p.consult(kb)
    return p

prolog = load_prolog()

def run_query(query_str: str):
    """
    Safe wrapper for Prolog queries.
    Returns a list of dict results, or an empty list.
    """
    try:
        return list(prolog.query(query_str))
    except Exception as e:
        # Helps debug malformed queries
        st.warning(f"Prolog query failed: {query_str}\nError: {e}")
        return []

# -------------------------------
# PATHS & LOGGING
# -------------------------------
APP_ROOT = Path(__file__).resolve().parent
LOG_DIR = APP_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
SESSION_LOG = LOG_DIR / "sessions.csv"


def log_session(query_drug_id, query_drug_label, conditions, current_meds_labels, warnings):
    """Append a simple log line for each check."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    cond_str = ";".join(conditions) if conditions else ""
    meds_str = ";".join(current_meds_labels) if current_meds_labels else ""
    warn_count = len(warnings)

    is_new_file = not SESSION_LOG.exists()
    with SESSION_LOG.open("a", encoding="utf-8") as f:
        if is_new_file:
            f.write("timestamp,query_drug_id,query_drug_label,conditions,current_meds,warnings_count\n")
        # crude CSV-safe: replace commas inside fields
        line = f"{timestamp},{query_drug_id},{query_drug_label.replace(',', ' ')},{cond_str.replace(',', ' ')},{meds_str.replace(',', ' ')},{warn_count}\n"
        f.write(line)


# -------------------------------
# DRUG INDEX (for autocomplete)
# -------------------------------
def build_drug_index():
    """
    Load all drugs from Prolog and build:
      - list of labels for UI (e.g., 'Ibuprofen (DB01050)')
      - mapping label -> id
      - mapping label -> atom_name
    """
    index = []
    for sol in prolog.query("drug(ID, Name)"):
        drug_id = sol["ID"]
        atom = sol["Name"]            # e.g. acetylsalicylic_acid
        label_name = atom.replace("_", " ").title()
        label = f"{label_name} ({drug_id})"
        index.append({"id": drug_id, "atom": atom, "label": label})

    index.sort(key=lambda x: x["label"])
    labels = [d["label"] for d in index]
    label_to_id = {d["label"]: d["id"] for d in index}
    label_to_atom = {d["label"]: d["atom"] for d in index}
    return labels, label_to_id, label_to_atom


DRUG_LABELS, LABEL_TO_ID, LABEL_TO_ATOM = build_drug_index()


# -------------------------------
# CONFIDENCE MAPPING
# -------------------------------
def severity_to_confidence(severity: str) -> str:
    """
    Map severity (minor/moderate/major) to a confidence label.
    This is a UI heuristic, not a statistical measure.
    """
    s = (severity or "").lower()
    if s == "major":
        return "HIGH"
    if s == "moderate":
        return "MED"
    if s == "minor":
        return "LOW"
    return "MED"


def confidence_badge(severity: str) -> str:
    """
    Render a simple text badge for confidence.
    """
    conf = severity_to_confidence(severity)
    if conf == "HIGH":
        return "🟥 **HIGH CONFIDENCE**"
    if conf == "MED":
        return "🟧 **MED CONFIDENCE**"
    if conf == "LOW":
        return "🟨 **LOW CONFIDENCE**"
    return "⬜ **UNKNOWN CONFIDENCE**"


# -------------------------------
# UI SETUP
# -------------------------------
st.set_page_config(page_title="Medication Safety Checker", layout="centered")

st.title("💊 Medication Safety Checker")
st.caption(
    "Rule-based medication safety using a Prolog knowledge base "
    "built from DrugBank XML and FDA label–aligned rules."
)

st.divider()

# -------------------------------
# USER PROFILE
# -------------------------------
st.header("🧑 Your Health Profile")

conditions = st.multiselect(
    "Select ongoing conditions:",
    [
        "renal_impairment",
        "hypertension",
        "diabetes",
        "hepatic_impairment",
        "cardiovascular_disease",
        "pregnancy",
        "asthma"
    ]
)

st.subheader("💊 Current Medications")
current_meds_labels = st.multiselect(
    "Start typing to search and select your ongoing medications:",
    DRUG_LABELS,
)

st.caption(
    "These medicines are shown based on the DrugBank-derived knowledge base. "
    "Selections represent what you are currently taking."
)

st.divider()

query_drug_label = st.selectbox(
    "❓ Which medicine do you want to check?",
    DRUG_LABELS,
    index=DRUG_LABELS.index(next((l for l in DRUG_LABELS if "Ibuprofen" in l), DRUG_LABELS[0]))
    if DRUG_LABELS else 0
)

# -------------------------------
# CHECK SAFETY
# -------------------------------
if st.button("🔍 Check Safety"):

    if not query_drug_label:
        st.error("Please select a medicine to check.")
        st.stop()

    query_drug_id = LABEL_TO_ID[query_drug_label]

    # Clear user facts in Prolog
    prolog.retractall("user_condition(_)")
    prolog.retractall("user_takes(_)")

    # Assert user profile (conditions)
    for c in conditions:
        prolog.assertz(f"user_condition({c})")

    # Assert current medications (by DrugBank ID)
    for label in current_meds_labels:
        med_id = LABEL_TO_ID.get(label)
        if med_id:
            prolog.assertz(f"user_takes('{med_id}')")

    st.subheader("⚠️ Safety Analysis")

    warnings = []

    # ---------------------------
    # Condition-based risks
    # ---------------------------
    for c in conditions:
        q = f"unsafe_for_condition('{query_drug_id}', {c})"
        if list(prolog.query(q)):
            warnings.append(
                f"• **Condition risk** — Not safe with *{c.replace('_',' ')}*."
            )

    # ---------------------------
# Drug–drug interactions with severity + explanation
# ---------------------------
    for label in current_meds_labels:
        other_id = LABEL_TO_ID.get(label)
        if not other_id:
            continue

    # --- Severity Query ---
        q = f"unsafe_context('{query_drug_id}', drug('{other_id}'), Severity)"
        interaction_results = run_query(q)

        for r in interaction_results:
            severity = r.get("Severity", "moderate")
            conf = confidence_badge(severity)

        # --- Explanation query ---
            expl_q = f"explain_unsafe('{query_drug_id}', drug('{other_id}'), Reason)"
            reason_res = run_query(expl_q)
            reason = reason_res[0]["Reason"] if reason_res else "interaction"

            warnings.append(
            f"• **Drug interaction** with *{label}* — "
            f"Severity: **{severity.upper()}** ({reason.replace('_',' ')}) "
            f"{conf}"
        )

    # ---------------------------
    # Food interactions + reasons
    # ---------------------------
    food_q = f"unsafe_with_food('{query_drug_id}', Food)"
    food_results = list(prolog.query(food_q))

    for r in food_results:
        food_atom = r["Food"]              # e.g. grapefruit
        food_name = str(food_atom).replace("_", " ")

        expl_q = f"explain_unsafe('{query_drug_id}', food({food_atom}), Reason)"
        reason_res = list(prolog.query(expl_q))
        reason = reason_res[0]["Reason"] if reason_res else "interaction"

        warnings.append(
            f"• **Food avoidance** — Avoid *{food_name}* "
            f"(Reason: {reason.replace('_', ' ')})."
        )

    # ---------------------------
    # Display Results
    # ---------------------------
    if warnings:
        st.error("Potential safety concerns detected:")
        for w in warnings:
            st.markdown(w)
    else:
        st.success("✅ No major safety risks detected based on your profile.")

    # Log this session
    log_session(
        query_drug_id=query_drug_id,
        query_drug_label=query_drug_label,
        conditions=conditions,
        current_meds_labels=current_meds_labels,
        warnings=warnings,
    )

    st.caption(
        "This tool provides educational safety warnings only and does not "
        "replace professional medical advice. Always consult a healthcare professional."
    )

    st.divider()

    # ---------------------------
    # SOURCES / CITATIONS BLOCK
    # ---------------------------
    with st.expander("📚 Data Sources & Clinical Alignment"):
        st.markdown(
            """
**Primary knowledge sources**

- **DrugBank XML** (exported dataset): used for medication identities, drug–drug interactions, and food interactions.
- **FDA Drug Labels** (via sections such as *Indications*, *Contraindications*, *Warnings and Precautions*): used to motivate contraindication and severity categories in the rules.
- **Clinical pharmacology principles** (e.g., CYP inhibition/induction, anticoagulant interactions, food effects like grapefruit, alcohol, dairy, and high-fat meals).

The Prolog rules encode a conservative subset of these safety concepts for explainable, rule-based reasoning.
            """
        )

    # ---------------------------
    # REVIEWER / SLIDE HINTS
    # ---------------------------
    with st.expander("📝 For Project Reviewers (Slide Summary Hints)"):
        st.markdown(
            """
Suggested slide structure:

1. **Problem Motivation**  
   - OTC misuse, polypharmacy, and lack of awareness of interactions.  
   - Real patients mixing painkillers, anticoagulants, and alcohol/food.

2. **Data & Knowledge Base**  
   - DrugBank XML → Extracted into Prolog facts (`drugs`, `interactions`, `food_interactions`, `contraindications`).  
   - FDA labels used as conceptual backing for age/condition/severity modeling.

3. **Architecture**  
   - Python + Streamlit UI  
   - Prolog engine (SWI-Prolog via PySWIP)  
   - Rule layer (`rules.pl`) combining food, drug–drug, and condition safety.

4. **Reasoning Examples**  
   - Ibuprofen + Aspirin → major bleeding risk.  
   - Warfarin + vitamin K foods → reduced anticoagulant effect.  
   - Pseudoephedrine + hypertension → condition-based risk.

5. **Explainability**  
   - `explain_unsafe/3` for “why” messages.  
   - Severity tiers (minor / moderate / major) + confidence badges.

6. **Limitations & Ethics**  
   - Decision-support only, not prescribing.  
   - Encourages consultation with healthcare professionals.
            """
        )
