import pandas as pd
import numpy as np
from io import BytesIO
from unidecode import unidecode


def clean_columns(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    data.columns = data.columns.str.strip()
    data.columns = data.columns.str.replace(" ", "_")
    data.columns = data.columns.str.lower()
    data.columns = [unidecode(col) for col in data.columns]
    data.columns = data.columns.str.replace(r"[^a-zA-Z0-9_]", "", regex=True)
    return data


def to_excel_bytes(sheets: dict) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    output.seek(0)
    return output.getvalue()


def process_ppna(df: pd.DataFrame, date_cloture_str: str = "2025-05-31"):
    data = df.copy()
    date_cloture = pd.Timestamp(date_cloture_str)

    if "%" in data.columns:
        data = data.drop(columns=["%"])

    data = clean_columns(data)

    data["effet"] = pd.to_datetime(data["effet"], dayfirst=True, errors="coerce")
    data["echeance"] = pd.to_datetime(data["echeance"], dayfirst=True, errors="coerce")
    data["prime_nette"] = pd.to_numeric(data["prime_nette"], errors="coerce").fillna(0)

    data["nb_de_jours_non_aquise"] = np.where(
        data["echeance"] <= date_cloture,
        0,
        (data["echeance"] - date_cloture).dt.days
    )

    data["nb_de_jours_contrat"] = (data["echeance"] - data["effet"]).dt.days + 1

    data["pourcentage"] = np.where(
        data["nb_de_jours_contrat"] > 0,
        data["nb_de_jours_non_aquise"] / data["nb_de_jours_contrat"],
        0
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
    data = clean_columns(df.copy())

    if "provision_degalisation" in data.columns:
        data.drop(columns=["provision_degalisation"], inplace=True)

    data["resultat_technique"] = pd.to_numeric(data["resultat_technique"], errors="coerce").fillna(0)
    data["charge_sinistre_n1"] = pd.to_numeric(data["charge_sinistre_n1"], errors="coerce").fillna(0)
    data["charge_sinistre_n2"] = pd.to_numeric(data["charge_sinistre_n2"], errors="coerce").fillna(0)
    data["charge_sinistre_n3"] = pd.to_numeric(data["charge_sinistre_n3"], errors="coerce").fillna(0)

    data["72pct_resultat_technique"] = 0.72 * data["resultat_technique"]

    data["moyenne_charge_sinistre_3_ans"] = (
        data[["charge_sinistre_n1", "charge_sinistre_n2", "charge_sinistre_n3"]]
        .mean(axis=1)
    )

    data["provision_degalisation"] = np.where(
        data["resultat_technique"] < 0,
        0,
        np.minimum(
            data["72pct_resultat_technique"],
            0.15 * data["moyenne_charge_sinistre_3_ans"]
        )
    )

    col_annee = "annees_dexercice" if "annees_dexercice" in data.columns else "annees_dexercice_"
    if col_annee not in data.columns:
        candidates = [c for c in data.columns if "annee" in c and "exercice" in c]
        if not candidates:
            raise ValueError("Colonne année d'exercice introuvable.")
        col_annee = candidates[0]

    synthese = (
        data.groupby([col_annee, "reseau", "produit"], dropna=False, as_index=False)["provision_degalisation"]
        .sum()
        .rename(columns={
            col_annee: "annees_exercice",
            "provision_degalisation": "PE"
        })
    )

    return data, synthese


def process_sap(df: pd.DataFrame, date_cloture_sap_str: str = "2025-03-31"):
    data = clean_columns(df.copy())
    date_cloture_sap = pd.Timestamp(date_cloture_sap_str)

    data["date_de_declaration"] = pd.to_datetime(
        data["date_de_declaration"], dayfirst=True, errors="coerce"
    )

    data["date_de_notification_reglement_rejet"] = pd.to_datetime(
        data["date_de_notification_reglement_rejet"], dayfirst=True, errors="coerce"
    )

    data["montant_sinistre_declare"] = pd.to_numeric(
        data["montant_sinistre_declare"], errors="coerce"
    ).fillna(0)

    data["montant_regle"] = pd.to_numeric(
        data["montant_regle"], errors="coerce"
    ).fillna(0)

    data["ecart_reglement"] = np.where(
        date_cloture_sap < data["date_de_declaration"],
        0,
        np.where(
            (date_cloture_sap > data["date_de_declaration"]) &
            (date_cloture_sap < data["date_de_notification_reglement_rejet"]),
            data["montant_sinistre_declare"],
            np.where(
                data["statut"].astype(str).str.strip().str.upper() == "REJET",
                0,
                data["montant_sinistre_declare"] - data["montant_regle"]
            )
        )
    )

    total_sap = pd.DataFrame({
        "indicateur": ["total_sap"],
        "valeur": [data["ecart_reglement"].sum()]
    })

    return data, total_sap


def calcul_ibnr_chain_ladder(df: pd.DataFrame,
                             col_annee_decl: str = "Année de déclaration",
                             col_annee_sin: str = "Année de sinistre",
                             col_montant: str = "le montant de sinistre"):

    data = df.copy()
    data = data[[col_annee_decl, col_annee_sin, col_montant]].dropna()
    data[col_annee_decl] = data[col_annee_decl].astype(int)
    data[col_annee_sin] = data[col_annee_sin].astype(int)
    data[col_montant] = pd.to_numeric(data[col_montant], errors="coerce").fillna(0.0)

    data["dev"] = data[col_annee_decl] - data[col_annee_sin]
    data = data[data["dev"] >= 0].copy()

    triangle_inc = pd.pivot_table(
        data,
        index=col_annee_sin,
        columns="dev",
        values=col_montant,
        aggfunc="sum",
        fill_value=0.0
    ).sort_index().sort_index(axis=1)

    triangle_cum = triangle_inc.cumsum(axis=1)

    dev_periods = list(triangle_cum.columns)
    facteurs = {}

    for j in range(len(dev_periods) - 1):
        d = dev_periods[j]
        d_next = dev_periods[j + 1]

        num = triangle_cum[d_next].sum()
        den = triangle_cum[d].sum()

        facteur = num / den if den != 0 else 1.0
        facteurs[d] = facteur

    facteurs_df = pd.DataFrame({
        "dev": list(facteurs.keys()),
        "facteur_age_to_age": list(facteurs.values())
    })

    triangle_proj = triangle_cum.copy()
    max_dev = max(dev_periods)

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
    resume.index.name = "Annee_de_sinistre"

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
    resume["ultime_estime"] = triangle_proj[max_dev]
    resume["IBNR"] = resume["ultime_estime"] - resume["cumul_observe"]

    ibnr_total = pd.DataFrame({
        "indicateur": ["IBNR_total"],
        "valeur": [resume["IBNR"].sum()]
    })

    return {
        "triangle_incremental": triangle_inc.reset_index(),
        "triangle_cumule": triangle_cum.reset_index(),
        "facteurs_developpement": facteurs_df,
        "triangle_projete_cumule": triangle_proj.reset_index(),
        "resume_ibnr": resume.reset_index(),
        "ibnr_total": ibnr_total
    }


def process_pb(df: pd.DataFrame):
    data = clean_columns(df.copy())

    data["solde_crediteur"] = pd.to_numeric(data["solde_crediteur"], errors="coerce").fillna(0)
    data["taux_pb"] = pd.to_numeric(data["taux_pb"], errors="coerce").fillna(0)

    data["participation_aux_benefices_du_solde_crediteur"] = np.where(
        data["beneficier_au_pn"].astype(str).str.strip().str.lower() == "non",
        0,
        np.where(
            data["solde_crediteur"] <= 0,
            0,
            data["taux_pb"] * data["solde_crediteur"]
        )
    )

    return data