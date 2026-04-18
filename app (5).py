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

st.set_page_config(page_title="Assurance Dashboard", layout="wide")

st.title("Dashboard Assurance")

tab_ppna, tab_pe, tab_sap, tab_ibnr, tab_pb = st.tabs(
    ["PPNA", "PE", "SAP", "IBNR", "PB"]
)

import streamlit as st
import pandas as pd
import plotly.express as px


