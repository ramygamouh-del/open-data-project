import streamlit as st
import pandas as pd
from processors import (
    process_ppna,
    process_pe,
    process_sap,
    process_pb,
    calcul_ibnr_chain_ladder,
    to_excel_bytes,
)

st.set_page_config(page_title="Assurance Toolkit", layout="wide")
st.title("Plateforme assurance")
st.write("Charge un fichier Excel ou CSV et lance le calcul souhaité.")

module = st.sidebar.selectbox(
    "Choisir un module",
    ["PPNA", "PE", "SAP", "IBNR", "PB"],
)

uploaded = st.file_uploader("Importer un fichier Excel ou CSV", type=["xlsx", "xls", "csv"])


def read_file(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

if uploaded is not None:
    df = read_file(uploaded)
    st.subheader("Aperçu")
    st.dataframe(df.head())

    try:
        if module == "PPNA":
            date_cloture = st.date_input("Date de clôture", value=pd.Timestamp("2025-05-31").date())
            if st.button("Calculer PPNA"):
                detail, synthese = process_ppna(df, str(date_cloture))
                st.subheader("Détail")
                st.dataframe(detail.head())
                st.subheader("Synthèse PPNA")
                st.dataframe(synthese)
                excel_bytes = to_excel_bytes({"detail_ppna": detail, "synthese_ppna": synthese})
                st.download_button("Télécharger Excel PPNA", excel_bytes, "ppna_resultats.xlsx")

        elif module == "PE":
            if st.button("Calculer PE"):
                detail, synthese = process_pe(df)
                st.subheader("Détail")
                st.dataframe(detail.head())
                if synthese is not None:
                    st.subheader("Synthèse PE")
                    st.dataframe(synthese)
                    excel_bytes = to_excel_bytes({"detail_pe": detail, "synthese_pe": synthese})
                else:
                    excel_bytes = to_excel_bytes({"detail_pe": detail})
                st.download_button("Télécharger Excel PE", excel_bytes, "pe_resultats.xlsx")

        elif module == "SAP":
            date_cloture_sap = st.date_input("Date de clôture SAP", value=pd.Timestamp("2025-03-31").date())
            if st.button("Calculer SAP"):
                detail, total = process_sap(df, str(date_cloture_sap))
                st.subheader("Détail SAP")
                st.dataframe(detail.head())
                st.subheader("Total SAP")
                st.dataframe(total)
                excel_bytes = to_excel_bytes({"detail_sap": detail, "total_sap": total})
                st.download_button("Télécharger Excel SAP", excel_bytes, "sap_resultats.xlsx")

        elif module == "IBNR":
            col_decl = st.text_input("Colonne année de déclaration", value="Année de déclaration")
            col_sin = st.text_input("Colonne année de sinistre", value="Année de sinistre")
            col_montant = st.text_input("Colonne montant", value="le montant de sinistre")
            if st.button("Calculer IBNR"):
                results = calcul_ibnr_chain_ladder(df, col_decl, col_sin, col_montant)
                st.subheader("Résumé IBNR")
                st.dataframe(results["resume_ibnr"])
                st.subheader("IBNR total")
                st.dataframe(results["ibnr_total"])
                excel_bytes = to_excel_bytes(results)
                st.download_button("Télécharger Excel IBNR", excel_bytes, "ibnr_resultats.xlsx")

        elif module == "PB":
            if st.button("Calculer PB"):
                detail = process_pb(df)
                st.subheader("Résultat PB")
                st.dataframe(detail.head())
                excel_bytes = to_excel_bytes({"detail_pb": detail})
                st.download_button("Télécharger Excel PB", excel_bytes, "pb_resultats.xlsx")

    except Exception as e:
        st.error(f"Erreur: {e}")
else:
    st.info("Importe un fichier pour commencer.")

import streamlit as st
import pandas as pd
import plotly.express as px
from processors import (
    process_ppna,
    process_pe,
    process_sap,
    process_pb,
    calcul_ibnr_chain_ladder,
    to_excel_bytes,
)

import streamlit as st
import pandas as pd
import plotly.express as px
from processors import process_ppna, process_pe, process_sap


# =========================================================
# CONFIGURATION GENERALE
# =========================================================
st.set_page_config(page_title="Dashboard Assurance", layout="wide")
st.title("Dashboard Assurance")


# =========================================================
# HELPERS
# =========================================================
def afficher_colonnes_manquantes(df, colonnes_requises):
    colonnes_manquantes = [c for c in colonnes_requises if c not in df.columns]
    if colonnes_manquantes:
        st.error(f"Colonnes manquantes : {colonnes_manquantes}")
        st.write("Colonnes disponibles :", df.columns.tolist())
        return True
    return False


# =========================================================
# 1) DASHBOARD PPNA
# =========================================================
def dashboard_ppna(detail_df, synthese_df=None):
    st.subheader("Dashboard PPNA")

    df = detail_df.copy()

    colonnes_requises = ["echeance", "prime_non_acquise", "produit", "reseau"]
    if afficher_colonnes_manquantes(df, colonnes_requises):
        return

    df["echeance"] = pd.to_datetime(df["echeance"], errors="coerce")
    df["prime_non_acquise"] = pd.to_numeric(df["prime_non_acquise"], errors="coerce").fillna(0)

    st.metric("Prime non acquise totale", f"{df['prime_non_acquise'].sum():,.2f}")

    col1, col2 = st.columns(2)

    with col1:
        reseaux = sorted(df["reseau"].dropna().astype(str).unique().tolist())
        choix_reseaux = st.multiselect(
            "Choisir le réseau",
            reseaux,
            default=reseaux,
            key="ppna_reseau",
        )

    with col2:
        produits = sorted(df["produit"].dropna().astype(str).unique().tolist())
        choix_produits = st.multiselect(
            "Choisir le produit",
            produits,
            default=produits,
            key="ppna_produit",
        )

    df_filtre = df[
        df["reseau"].astype(str).isin(choix_reseaux) &
        df["produit"].astype(str).isin(choix_produits)
    ].copy()

    serie_temps = (
        df_filtre.groupby("echeance", as_index=False)["prime_non_acquise"]
        .sum()
        .sort_values("echeance")
    )

    fig_temps = px.line(
        serie_temps,
        x="echeance",
        y="prime_non_acquise",
        markers=True,
        title="Prime non acquise selon l'échéance",
    )
    st.plotly_chart(fig_temps, use_container_width=True)

    pie_data = (
        df_filtre.groupby("produit", as_index=False)["prime_non_acquise"]
        .sum()
        .sort_values("prime_non_acquise", ascending=False)
    )

    fig_pie = px.pie(
        pie_data,
        names="produit",
        values="prime_non_acquise",
        title="Répartition de la prime non acquise par produit",
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    bar_data = (
        df_filtre.groupby("reseau", as_index=False)["prime_non_acquise"]
        .sum()
        .sort_values("prime_non_acquise", ascending=False)
    )

    fig_bar = px.bar(
        bar_data,
        x="reseau",
        y="prime_non_acquise",
        title="Prime non acquise par réseau",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Données filtrées")
    st.dataframe(df_filtre, use_container_width=True)

    if synthese_df is not None:
        st.subheader("Synthèse PPNA")
        st.dataframe(synthese_df, use_container_width=True)


# =========================================================
# 2) DASHBOARD PE
# =========================================================
def dashboard_pe(detail_df, synthese_df=None):
    st.subheader("Dashboard Provision d'égalisation")

    df = detail_df.copy()

    colonnes_requises = ["produit", "provision_degalisation"]
    if afficher_colonnes_manquantes(df, colonnes_requises):
        return

    col_annee = None
    for c in ["annees_dexercice", "annees_exercice", "annee_exercice"]:
        if c in df.columns:
            col_annee = c
            break

    if col_annee is None:
        st.error("Colonne année d'exercice introuvable.")
        st.write("Colonnes disponibles :", df.columns.tolist())
        return

    df["provision_degalisation"] = pd.to_numeric(
        df["provision_degalisation"], errors="coerce"
    ).fillna(0)

    dates_test = pd.to_datetime(df[col_annee], dayfirst=True, errors="coerce")
    if dates_test.notna().sum() > 0:
        df[col_annee] = dates_test.dt.year.fillna(df[col_annee])

    df[col_annee] = pd.to_numeric(df[col_annee], errors="coerce")

    st.metric("Provision d'égalisation totale", f"{df['provision_degalisation'].sum():,.2f}")

    col1, col2 = st.columns(2)

    with col1:
        if "reseau" in df.columns:
            reseaux = sorted(df["reseau"].dropna().astype(str).unique().tolist())
            choix_reseaux = st.multiselect(
                "Filtrer par réseau",
                reseaux,
                default=reseaux,
                key="pe_reseau",
            )
            df = df[df["reseau"].astype(str).isin(choix_reseaux)]

    with col2:
        produits = sorted(df["produit"].dropna().astype(str).unique().tolist())
        choix_produits = st.multiselect(
            "Filtrer par produit",
            produits,
            default=produits,
            key="pe_produit",
        )
        df = df[df["produit"].astype(str).isin(choix_produits)]

    pie_data = (
        df.groupby("produit", as_index=False)["provision_degalisation"]
        .sum()
        .sort_values("provision_degalisation", ascending=False)
    )

    fig_pie = px.pie(
        pie_data,
        names="produit",
        values="provision_degalisation",
        title="Répartition de la provision d'égalisation par produit",
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    time_data = (
        df.groupby(col_annee, as_index=False)["provision_degalisation"]
        .sum()
        .sort_values(col_annee)
    )

    fig_time = px.line(
        time_data,
        x=col_annee,
        y="provision_degalisation",
        markers=True,
        title="Provision d'égalisation selon l'année d'exercice",
    )
    st.plotly_chart(fig_time, use_container_width=True)

    st.subheader("Données filtrées")
    st.dataframe(df, use_container_width=True)

    if synthese_df is not None:
        st.subheader("Synthèse PE")
        st.dataframe(synthese_df, use_container_width=True)


# =========================================================
# 3) DASHBOARD SAP
# =========================================================
def dashboard_sap(detail_df, total_df=None):
    st.subheader("Dashboard SAP")

    df = detail_df.copy()

    col_agence = None
    for c in ["agence", "agences"]:
        if c in df.columns:
            col_agence = c
            break

    col_annee_survenance = None
    for c in [
        "annee_de_survenance_de_sinistre",
        "annee_de_survenance_de_sinsitre",
    ]:
        if c in df.columns:
            col_annee_survenance = c
            break

    if col_agence is None:
        st.error("Colonne agence/agences introuvable.")
        st.write("Colonnes disponibles :", df.columns.tolist())
        return

    colonnes_requises = [col_agence, "montant_sinistre_declare", "statut"]
    if afficher_colonnes_manquantes(df, colonnes_requises):
        return

    if col_annee_survenance is None:
        st.error("Colonne année de survenance du sinistre introuvable.")
        st.write("Colonnes disponibles :", df.columns.tolist())
        return

    df["montant_sinistre_declare"] = pd.to_numeric(
        df["montant_sinistre_declare"], errors="coerce"
    ).fillna(0)

    df[col_annee_survenance] = pd.to_numeric(
        df[col_annee_survenance], errors="coerce"
    )

    df[col_agence] = df[col_agence].astype(str)
    df["statut"] = df["statut"].astype(str)

    st.metric("Montant total sinistre déclaré", f"{df['montant_sinistre_declare'].sum():,.2f}")

    if total_df is not None and "valeur" in total_df.columns:
        st.metric("Total SAP", f"{total_df['valeur'].iloc[0]:,.2f}")

    col1, col2 = st.columns(2)

    with col1:
        agences = sorted(df[col_agence].dropna().unique().tolist())
        choix_agences = st.multiselect(
            "Filtrer par agence",
            agences,
            default=agences,
            key="sap_agence",
        )

    with col2:
        statuts = sorted(df["statut"].dropna().unique().tolist())
        choix_statuts = st.multiselect(
            "Filtrer par statut",
            statuts,
            default=statuts,
            key="sap_statut",
        )

    df_filtre = df[
        df[col_agence].isin(choix_agences) &
        df["statut"].isin(choix_statuts)
    ].copy()

    agence_data = (
        df_filtre.groupby(col_agence, as_index=False)["montant_sinistre_declare"]
        .sum()
        .sort_values("montant_sinistre_declare", ascending=False)
    )

    fig_bar = px.bar(
        agence_data,
        x=col_agence,
        y="montant_sinistre_declare",
        title="Répartition du montant sinistre déclaré par agence",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    time_data = (
        df_filtre.groupby(col_annee_survenance, as_index=False)["montant_sinistre_declare"]
        .sum()
        .sort_values(col_annee_survenance)
    )

    fig_time = px.line(
        time_data,
        x=col_annee_survenance,
        y="montant_sinistre_declare",
        markers=True,
        title="Montant sinistre déclaré selon l'année de survenance du sinistre",
    )
    st.plotly_chart(fig_time, use_container_width=True)

    statut_data = (
        df_filtre.groupby("statut", as_index=False)
        .size()
        .rename(columns={"size": "frequence"})
        .sort_values("frequence", ascending=False)
    )

    fig_pie = px.pie(
        statut_data,
        names="statut",
        values="frequence",
        title="Répartition des statuts",
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("Données SAP filtrées")
    st.dataframe(df_filtre, use_container_width=True)


# =========================================================
# ONGLETS
# =========================================================
tab_ppna, tab_pe, tab_sap = st.tabs(["PPNA", "PE", "SAP"])


# =========================================================
# CONTENU ONGLET PPNA
# =========================================================
with tab_ppna:
    fichier_ppna = st.file_uploader(
        "Charger le fichier PPNA",
        type=["xlsx", "csv"],
        key="ppna",
    )

    if fichier_ppna:
        try:
            df_ppna = (
                pd.read_excel(fichier_ppna)
                if fichier_ppna.name.endswith(".xlsx")
                else pd.read_csv(fichier_ppna)
            )
            detail_ppna, synthese_ppna = process_ppna(df_ppna)
            dashboard_ppna(detail_ppna, synthese_ppna)
        except Exception as e:
            st.error(f"Erreur PPNA : {e}")


# =========================================================
# CONTENU ONGLET PE
# =========================================================
with tab_pe:
    fichier_pe = st.file_uploader(
        "Charger le fichier PE",
        type=["xlsx", "csv"],
        key="pe",
    )

    if fichier_pe:
        try:
            df_pe = (
                pd.read_excel(fichier_pe)
                if fichier_pe.name.endswith(".xlsx")
                else pd.read_csv(fichier_pe)
            )
            detail_pe, synthese_pe = process_pe(df_pe)
            dashboard_pe(detail_pe, synthese_pe)
        except Exception as e:
            st.error(f"Erreur PE : {e}")


# =========================================================
# CONTENU ONGLET SAP
# =========================================================
with tab_sap:
    fichier_sap = st.file_uploader(
        "Charger le fichier SAP",
        type=["xlsx", "csv"],
        key="sap",
    )

    if fichier_sap:
        try:
            df_sap = (
                pd.read_excel(fichier_sap)
                if fichier_sap.name.endswith(".xlsx")
                else pd.read_csv(fichier_sap)
            )
            detail_sap, total_sap = process_sap(df_sap)
            dashboard_sap(detail_sap, total_sap)
        except Exception as e:
            st.error(f"Erreur SAP : {e}")
