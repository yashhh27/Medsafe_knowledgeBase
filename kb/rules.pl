%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% RULES.PL — CLINICAL SAFETY REASONING ENGINE
%% Contains ONLY inference logic.
%%
%% FACT SOURCES:
%%    - food_interactions.pl      : food_interaction/3, food_note/2
%%    - drug_interactions.pl      : interaction/3
%%    - contraindications.pl      : contraindicated/2
%%    - classes.pl (optional)     : drug_class/2, class_interaction/3
%%
%% SAFETY DIMENSIONS:
%%  1. Food–Drug interactions
%%  2. Drug–Drug interactions
%%  3. Drug–Condition contraindications
%%  4. Class–Class interactions (optional)
%%  5. Severity scoring
%%  6. Explainability for UI
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% NORMALIZATION LAYER
%% Convert any input form to canonical DrugBank ID atom.
%% Your facts use uppercase IDs like 'DB00682', so we normalize to that.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

normalize_drug(Raw, Normalized) :-
    % Convert strings to atoms if needed
    (   atom(Raw)
    ->  Atom = Raw
    ;   atom_string(Atom, Raw)
    ),
    % Canonical form: UPPERCASE (matches your facts files)
    upcase_atom(Atom, Normalized).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% SEVERITY MAPPING
%% Map mechanism/effect labels -> severity tier.
%% Extend this table to fit your dataset.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

severity(bleeding_risk,                  major).
severity(increased_anticoagulant_effect, major).
severity(reduced_anticoagulant_effect,   major).
severity(increased_drug_level,           major).
severity(liver_toxicity,                 major).

severity(enzyme_inhibition,              moderate).
severity(enzyme_induction,               moderate).
severity(interaction,                    moderate).   % generic fallback

severity(reduced_effect,                 minor).
severity(increased_effect,               minor).
severity(mild_interaction,               minor).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% DRUG–DRUG SAFETY
%%  - interaction/3 comes from drug_interactions.pl:
%%        interaction(DrugA, DrugB, Effect).
%%  - We provide:
%%        drug_interaction_effect/3   (symmetric, normalized)
%%        unsafe_drug_combo/2         (no severity, just "unsafe pair")
%%        unsafe_context/3            (Severity for Python)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%% Symmetric, normalized lookup of the raw effect
drug_interaction_effect(RawA, RawB, Effect) :-
    normalize_drug(RawA, A),
    normalize_drug(RawB, B),
    interaction(A, B, Effect).

drug_interaction_effect(RawA, RawB, Effect) :-
    normalize_drug(RawA, A),
    normalize_drug(RawB, B),
    interaction(B, A, Effect).

%% Simple "is this combination unsafe?"
unsafe_drug_combo(RawA, RawB) :-
    drug_interaction_effect(RawA, RawB, _).

%% Internal: compute severity for all possible paths (may contain duplicates)
unsafe_context_raw(RawA, RawB, Severity) :-
    drug_interaction_effect(RawA, RawB, Effect),
    severity(Effect, Severity).

%% Public API used by Python:
%%    unsafe_context('DB01050', drug('DB00682'), Severity).
%% Duplicate severities are removed via setof/3.
unsafe_context(RawA, drug(RawB), Severity) :-
    setof(S, unsafe_context_raw(RawA, RawB, S), SevList),
    member(Severity, SevList).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% DRUG–CONDITION CONTRAINDICATIONS
%% contraindicated/2 comes from contraindications.pl:
%%     contraindicated(DrugID, ConditionAtom).
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

unsafe_for_condition(RawDrug, Condition) :-
    normalize_drug(RawDrug, Drug),
    contraindicated(Drug, Condition).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% FOOD–DRUG SAFETY
%% food_interaction/3, food_note/2 come from food_interactions.pl:
%%     food_interaction(DrugID, FoodAtom, Effect).
%%     food_note(DrugID, Note).
%%
%% We intentionally *do not* inherit other drugs food risks via
%% interaction/3, to avoid over-warning (Warfarin vs. NSAIDs example).
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%% Raw: may contain duplicates if facts are duplicated
unsafe_with_food_raw(RawDrug, Food) :-
    normalize_drug(RawDrug, Drug),
    food_interaction(Drug, Food, _).

%% Public API used by Python:
%%   unsafe_with_food('DB01050', Food).
%% Returns each Food only once.
unsafe_with_food(RawDrug, Food) :-
    setof(F, unsafe_with_food_raw(RawDrug, F), Foods),
    member(Food, Foods).

%% "Has any non-blocking food guidance?"
has_food_guidance(RawDrug) :-
    normalize_drug(RawDrug, Drug),
    food_note(Drug, _).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% CLASS–BASED INTERACTIONS  (optional)
%% Requires:
%%    drug_class/2        : drug_class(DrugID, ClassAtom).
%%    class_interaction/3 : class_interaction(ClassA, ClassB, Effect).
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

unsafe_class_interaction(RawA, RawB, Effect) :-
    normalize_drug(RawA, A),
    normalize_drug(RawB, B),
    drug_class(A, ClassA),
    drug_class(B, ClassB),
    class_interaction(ClassA, ClassB, Effect).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% COMBINED UNSAFE CONTEXT (2-ARITY, DIMENSION-ONLY VIEW)
%% Not used directly by your Python UI, but useful for queries like:
%%    unsafe_context('DB01050', food(F)).
%%    unsafe_context('DB01050', condition(C)).
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

unsafe_context(RawDrug, food(Food)) :-
    unsafe_with_food(RawDrug, Food).

unsafe_context(RawDrug, condition(Cond)) :-
    unsafe_for_condition(RawDrug, Cond).

unsafe_context(RawA, drug(RawB)) :-
    unsafe_drug_combo(RawA, RawB).

unsafe_context(RawDrug, class(Class)) :-
    normalize_drug(RawDrug, Drug),
    drug_class(Drug, Class).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% COMBINED UNSAFE CONTEXT (3-ARITY, WITH SEVERITY)
%% Currently we only attach severity to:
%%   - drug–drug interactions
%%   - class–class interactions (optional)
%% Food + condition severities can be added later if desired.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%% Drug–drug severity (main one used by Streamlit)
%% already defined above:
%%    unsafe_context(RawA, drug(RawB), Severity).

%% Class–class severity (optional, if you use class_interaction/3)
unsafe_context(RawDrug, class(ClassB), Severity) :-
    normalize_drug(RawDrug, Drug),
    drug_class(Drug, ClassA),
    class_interaction(ClassA, ClassB, Effect),
    severity(Effect, Severity).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% SAFETY & RISK CLASSIFICATION (OPTIONAL HELPERS)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%% A drug is considered "safe" if we cannot derive any unsafe context.
safe_drug(RawDrug) :-
    normalize_drug(RawDrug, Drug),
    \+ unsafe_context(Drug, _).

%% High-risk: contraindicated and at least one more risk dimension.
high_risk_drug(RawDrug) :-
    unsafe_for_condition(RawDrug, _),
    unsafe_with_food(RawDrug, _).

high_risk_drug(RawDrug) :-
    unsafe_for_condition(RawDrug, _),
    unsafe_drug_combo(RawDrug, _).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% EXPLAINABILITY (for UI output)
%%
%% These predicates provide *reasons* for each unsafe dimension.
%% Python calls them like:
%%    explain_unsafe('DB01050', drug('DB00682'), Reason).
%%    explain_unsafe('DB01050', food(grapefruit), Reason).
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%% Food reason: why is this food unsafe with this drug?
explain_unsafe(RawDrug, food(Food), Reason) :-
    normalize_drug(RawDrug, Drug),
    food_interaction(Drug, Food, Reason).

%% Drug–drug reason: mechanism/effect label from interaction/3
explain_unsafe(RawA, drug(RawB), Effect) :-
    drug_interaction_effect(RawA, RawB, Effect).

%% Condition reason: simply "contraindicated"
explain_unsafe(RawDrug, condition(Cond), contraindicated) :-
    unsafe_for_condition(RawDrug, Cond).

%% Class–class reason (optional)
explain_unsafe(RawDrug, class(ClassB), Effect) :-
    normalize_drug(RawDrug, Drug),
    drug_class(Drug, ClassA),
    class_interaction(ClassA, ClassB, Effect).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% END OF RULES.PL
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
