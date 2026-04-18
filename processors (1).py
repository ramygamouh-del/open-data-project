import pandas as pd
import numpy as np
from io import BytesIO
from unidecode import unidecode


def clean_columns(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    data.columns = data.columns.str.strip()
    data.columns = data.columns.str.replace(' ', '_', regex=False)
    data.columns = data.columns.str.lower()
    data.columns = [unidecode(str(col)) for col in data.columns]
    data.columns = data.columns.str.replace(r'[^a-zA-Z0-9_]', '', regex=True)
    return data


def to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            safe_name = str(name)[:31] if name else "Sheet1"
            df.to_excel(writer, sheet_name=safe_name, index=False)
    output.seek(0)
    return output.getvalue()


def process_ppna(df: pd.DataFrame, date_cloture: str = "2025-05-31"):
    data = df.copy()
    if "%" in data.columns:
        data = data.drop(columns=["%"])
    data = clean_columns(data)

    required = ["effet", "echeance", "prime_nette", "reseau", "produit"]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour PPNA: {missing}")

    date_cloture_ts = pd.Timestamp(date_cloture)
    data["effet"] = pd.to_datetime(data["effet"], dayfirst=True, errors="coerce")
    data["echeance"] = pd.to_datetime(data["echeance"], dayfirst=True, errors="coerce")
    data["prime_nette"] = pd.to_numeric(data["prime_nette"], errors="coerce")

    data["nb_de_jours_non_aquise"] = np.where(
        data["echeance"] <= date_cloture_ts,
        0,
        (data["echeance"] - date_cloture_ts).dt.days,
    )
    data["nb_de_jours_contrat"] = (data["echeance"] - data["effet"]).dt.days + 1
    data["pourcentage"] = np.where(
        data["nb_de_jours_contrat"] > 0,
        data["nb_de_jours_non_aquise"] / data["nb_de_jours_contrat"],
        0,
    )
    data["prime_non_acquise"] = data["prime_nette"] * data["pourcentage"]
    data["annee_effet"] = data["effet"].dt.year

    synthese = (
        data.groupby(["annee_effet", "reseau", "produit"], dropna=False, as_index=False)["prime_non_acquise"]
        .sum()
        .rename(columns={"prime_non_acquise": "PPNA"})
    )
    return data, synthese


def process_pe(df: pd.DataFrame):
    data = clean_columns(df)

    required = [
        "resultat_technique",
        "charge_sinistre_n1",
        "charge_sinistre_n2",
        "charge_sinistre_n3",
    ]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour PE: {missing}")

    if "provision_degalisation" in data.columns:
        data = data.drop(columns=["provision_degalisation"])

    for col in required:
        data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0)

    data["72pct_resultat_technique"] = 0.72 * data["resultat_technique"]
    data["moyenne_charge_sinistre_3_ans"] = data[[
        "charge_sinistre_n1", "charge_sinistre_n2", "charge_sinistre_n3"
    ]].mean(axis=1)
    data["provision_degalisation"] = np.where(
        data["resultat_technique"] < 0,
        0,
        np.minimum(
            data["72pct_resultat_technique"],
            0.15 * data["moyenne_charge_sinistre_3_ans"],
        ),
    )

    synthese = None
    if all(c in data.columns for c in ["annees_dexercice", "reseau", "produit"]):
        synthese = (
            data.groupby(["annees_dexercice", "reseau", "produit"], dropna=False, as_index=False)["provision_degalisation"]
            .sum()
            .rename(columns={"provision_degalisation": "PE"})
        )
    return data, synthese


def process_sap(df: pd.DataFrame, date_cloture_sap: str = "2025-03-31"):
    data = clean_columns(df)
    required = [
        "date_de_declaration",
        "date_de_notification_reglement_rejet",
        "montant_sinistre_declare",
        "montant_regle",
        "statut",
    ]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour SAP: {missing}")

    date_cloture = pd.Timestamp(date_cloture_sap)
    data["date_de_declaration"] = pd.to_datetime(data["date_de_declaration"], dayfirst=True, errors="coerce")
    data["date_de_notification_reglement_rejet"] = pd.to_datetime(
        data["date_de_notification_reglement_rejet"], dayfirst=True, errors="coerce"
    )
    data["montant_sinistre_declare"] = pd.to_numeric(data["montant_sinistre_declare"], errors="coerce").fillna(0)
    data["montant_regle"] = pd.to_numeric(data["montant_regle"], errors="coerce").fillna(0)

    data["ecart_reglement"] = np.where(
        date_cloture < data["date_de_declaration"],
        0,
        np.where(
            (date_cloture > data["date_de_declaration"]) &
            (date_cloture < data["date_de_notification_reglement_rejet"]),
            data["montant_sinistre_declare"],
            np.where(
                data["statut"].astype(str).str.strip().str.upper() == "REJET",
                0,
                data["montant_sinistre_declare"] - data["montant_regle"],
            ),
        ),
    )

    total = pd.DataFrame({"indicateur": ["total_sap"], "valeur": [data["ecart_reglement"].sum()]})
    return data, total


def process_pb(df: pd.DataFrame):
    data = clean_columns(df)
    required = ["beneficier_au_pn", "solde_crediteur", "taux_pb"]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour PB: {missing}")

    data["solde_crediteur"] = pd.to_numeric(data["solde_crediteur"], errors="coerce").fillna(0)
    data["taux_pb"] = pd.to_numeric(data["taux_pb"], errors="coerce").fillna(0)

    data["participation_aux_benefices_du_solde_crediteur"] = np.where(
        data["beneficier_au_pn"].astype(str).str.strip().str.lower() == "non",
        0,
        np.where(
            data["solde_crediteur"] <= 0,
            0,
            data["taux_pb"] * data["solde_crediteur"],
        ),
    )
    return data


def calcul_ibnr_chain_ladder(df: pd.DataFrame,
                             col_annee_decl: str = "Annee_de_declaration",
                             col_annee_sin: str = "Annee_de_sinistre",
                             col_montant: str = "le_montant_de_sinistre"):
    data = clean_columns(df)
    cols = [clean_columns(pd.DataFrame(columns=[col_annee_decl, col_annee_sin, col_montant])).columns[0],
            clean_columns(pd.DataFrame(columns=[col_annee_decl, col_annee_sin, col_montant])).columns[1],
            clean_columns(pd.DataFrame(columns=[col_annee_decl, col_annee_sin, col_montant])).columns[2]]
    col_annee_decl_c, col_annee_sin_c, col_montant_c = cols
    required = [col_annee_decl_c, col_annee_sin_c, col_montant_c]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour IBNR: {missing}")

    data = data[[col_annee_decl_c, col_annee_sin_c, col_montant_c]].dropna().copy()
    data[col_annee_decl_c] = pd.to_numeric(data[col_annee_decl_c], errors="coerce").astype("Int64")
    data[col_annee_sin_c] = pd.to_numeric(data[col_annee_sin_c], errors="coerce").astype("Int64")
    data[col_montant_c] = pd.to_numeric(data[col_montant_c], errors="coerce").fillna(0.0)
    data = data.dropna(subset=[col_annee_decl_c, col_annee_sin_c]).copy()
    data[col_annee_decl_c] = data[col_annee_decl_c].astype(int)
    data[col_annee_sin_c] = data[col_annee_sin_c].astype(int)

    data["dev"] = data[col_annee_decl_c] - data[col_annee_sin_c]
    data = data[data["dev"] >= 0].copy()

    triangle_inc = pd.pivot_table(
        data,
        index=col_annee_sin_c,
        columns="dev",
        values=col_montant_c,
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index().sort_index(axis=1)

    triangle_cum = triangle_inc.cumsum(axis=1)
    dev_periods = list(triangle_cum.columns)
    facteurs = {}
    for j in range(len(dev_periods) - 1):
        d = dev_periods[j]
        d_next = dev_periods[j + 1]
        den = triangle_cum[d].sum()
        num = triangle_cum[d_next].sum()
        facteurs[d] = num / den if den != 0 else 1.0

    facteurs_df = pd.DataFrame({
        "dev": list(facteurs.keys()),
        "facteur_age_to_age": list(facteurs.values()),
    })

    triangle_proj = triangle_cum.copy()
    max_dev = max(dev_periods) if dev_periods else 0
    for i in triangle_proj.index:
        row = triangle_proj.loc[i].copy()
        observed_devs = [d for d in dev_periods if pd.notna(row[d]) and row[d] != 0]
        if len(observed_devs) == 0:
            continue
        last_obs = max(observed_devs)
        current_val = row[last_obs]
        for d in dev_periods:
            if d > last_obs:
                prev_d = d - 1
                if prev_d in facteurs:
                    current_val = current_val * facteurs[prev_d]
                triangle_proj.loc[i, d] = current_val

    resume = pd.DataFrame(index=triangle_proj.index)
    resume.index.name = "annee_de_sinistre"
    last_observed = []
    cumule_observe = []
    for i in triangle_cum.index:
        row = triangle_cum.loc[i]
        observed = [d for d in triangle_cum.columns if pd.notna(row[d]) and row[d] != 0]
        if len(observed) == 0:
            last_observed.append(np.nan)
            cumule_observe.append(0.0)
        else:
            d_last = max(observed)
            last_observed.append(d_last)
            cumule_observe.append(row[d_last])

    resume["dernier_dev_observe"] = last_observed
    resume["cumul_observe"] = cumule_observe
    resume["ultime_estime"] = triangle_proj[max_dev] if len(dev_periods) else 0.0
    resume["ibnr"] = resume["ultime_estime"] - resume["cumul_observe"]
    resume = resume.reset_index()
    ibnr_total = float(resume["ibnr"].sum()) if not resume.empty else 0.0
    total_df = pd.DataFrame({"indicateur": ["IBNR total"], "valeur": [ibnr_total]})

    return {
        "triangle_incremental": triangle_inc.reset_index(),
        "triangle_cumule": triangle_cum.reset_index(),
        "facteurs_developpement": facteurs_df,
        "triangle_projete_cumule": triangle_proj.reset_index(),
        "resume_ibnr": resume,
        "ibnr_total": total_df,
    }
