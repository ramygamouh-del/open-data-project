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
st.title("Déploiement assurance")
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

st.set_page_config(page_title="Assurance Dashboard", layout="wide")

st.title("Plateforme Assurance")

tab_ppna, tab_pe, tab_sap, tab_ibnr, tab_pb = st.tabs(
    ["PPNA", "PE", "SAP", "IBNR", "PB"]
)

def dashboard_ppna(detail_df, synthese_df):
    st.subheader("Dashboard PPNA")

    # Copie de travail
    df = detail_df.copy()

    # Vérifications / conversions
    if "echeance" in df.columns:
        df["echeance"] = pd.to_datetime(df["echeance"], errors="coerce")

    if "prime_non_acquise" in df.columns:
        df["prime_non_acquise"] = pd.to_numeric(df["prime_non_acquise"], errors="coerce").fillna(0)

    # KPI
    total_ppna = df["prime_non_acquise"].sum() if "prime_non_acquise" in df.columns else 0
    st.metric("PPNA totale", f"{total_ppna:,.2f}")

    # Filtres
    colf1, colf2 = st.columns(2)

    with colf1:
        if "reseau" in df.columns:
            liste_reseaux = sorted(df["reseau"].dropna().astype(str).unique().tolist())
            choix_reseaux = st.multiselect("Filtrer par réseau", liste_reseaux, default=liste_reseaux)
            df = df[df["reseau"].astype(str).isin(choix_reseaux)]

    with colf2:
        if "produit" in df.columns:
            liste_produits = sorted(df["produit"].dropna().astype(str).unique().tolist())
            choix_produits = st.multiselect("Filtrer par produit", liste_produits, default=liste_produits)
            df = df[df["produit"].astype(str).isin(choix_produits)]

    # 1) Relation prime_non_acquise ~ echeance (temps)
    if {"echeance", "prime_non_acquise"}.issubset(df.columns):
        serie_temps = (
            df.groupby("echeance", as_index=False)["prime_non_acquise"]
            .sum()
            .sort_values("echeance")
        )

        fig_time = px.line(
            serie_temps,
            x="echeance",
            y="prime_non_acquise",
            markers=True,
            title="Prime non acquise selon l'échéance"
        )
        st.plotly_chart(fig_time, use_container_width=True)

    # 2) Pie chart sur produit
    if {"produit", "prime_non_acquise"}.issubset(df.columns):
        pie_data = (
            df.groupby("produit", as_index=False)["prime_non_acquise"]
            .sum()
            .sort_values("prime_non_acquise", ascending=False)
        )

        fig_pie = px.pie(
            pie_data,
            names="produit",
            values="prime_non_acquise",
            title="Répartition de la prime non acquise par produit"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # 3) Bar plot sur réseau
    if {"reseau", "prime_non_acquise"}.issubset(df.columns):
        bar_data = (
            df.groupby("reseau", as_index=False)["prime_non_acquise"]
            .sum()
            .sort_values("prime_non_acquise", ascending=False)
        )

        fig_bar = px.bar(
            bar_data,
            x="reseau",
            y="prime_non_acquise",
            title="Prime non acquise par réseau"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Tableau de synthèse
    st.subheader("Données détaillées")
    st.dataframe(df, use_container_width=True)

    if synthese_df is not None:
        st.subheader("Synthèse PPNA")
        st.dataframe(synthese_df, use_container_width=True)
