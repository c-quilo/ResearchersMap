import streamlit as st
st.set_page_config(layout="wide")
import pandas as pd
from pyvis.network import Network
from itertools import combinations
from collections import defaultdict
import streamlit.components.v1 as components
from pathlib import Path
import ast
import os
from PIL import Image


st.sidebar.markdown("""
    <style>
    .logo-dark { display: none; }
    .logo-light { display: block; }

    @media (prefers-color-scheme: dark) {
        .logo-dark { display: block; }
        .logo-light { display: none; }
    }
    </style>

    <div class="logo-light">
        <img src="logo/logo_light.png" width="100%%">
    </div>
    <div class="logo-dark">
        <img src="logo/logo_dark.png" width="100%%">
    </div>
""", unsafe_allow_html=True)
st.sidebar.title("📁 Select or Upload Data")

# Preloaded CSVs
preloaded_files = {
    "Non-toxic pesticide substitutes": "data/Challenge_1.csv",
    "Alternatives to endocrine disruptors": "data/Challenge_3.csv",
    "Removing endocrine disruptors": "data/Challenge_4.csv",

}

selected_preloaded = st.sidebar.selectbox("Choose a preloaded dataset:", ["None"] + list(preloaded_files.keys()))

researcher_file = st.sidebar.file_uploader("Or upload your own researcher CSV", type="csv")

if researcher_file is not None:
    df = pd.read_csv(researcher_file)
elif selected_preloaded != "None":
    df = pd.read_csv(preloaded_files[selected_preloaded])
else:
    st.title("🌎 Researcher Network Explorer for Environmental Pollution")
    st.info("👈 Use the sidebar to set filters and generate the network.")
    st.stop()

# --- Sidebar: Filters ---
available_countries = sorted(df["country_code"].dropna().unique())
select_all = st.sidebar.checkbox("🌍 Select all countries", value=True)

if select_all:
    selected_countries = st.sidebar.multiselect("Countries", available_countries, default=available_countries)
else:
    selected_countries = st.sidebar.multiselect("Countries", available_countries)

available_roles = ["PI", "PhD/ECR", "Researcher"]
selected_roles = st.sidebar.multiselect("Filter by role", available_roles, default=available_roles)
top_n = st.sidebar.slider("🔝 Show top N researchers", min_value=10, max_value=len(df), value=min(100, len(df)), step=1)

generate = st.sidebar.button("🚀 Generate Network")

st.title("🌎 Researcher Network Explorer for Environmental Pollution")

if generate:
    if not selected_countries:
        st.warning("Please select at least one country.")
        st.stop()

    def get_role(row):
        if pd.notna(row["active_since"]) and pd.notna(row["works_count"]):
            if row["active_since"] <= 2022 and row["works_count"] > 50:
                return "PI"
            elif row["active_since"] == 2022 and row["works_count"] < 5:
                return "PhD/ECR"
        return "Researcher"

    df["role"] = df.apply(get_role, axis=1)
    df = df[df["country_code"].isin(selected_countries) & df["role"].isin(selected_roles)]
    df = df.sort_values(by="number_of_works", ascending=False).head(top_n)

    net = Network(height="100vh", width="100%", bgcolor="white", font_color="black", notebook=False)
    net.force_atlas_2based(gravity=-50)

    author_names = set(df["display_name"])
    added_institutions = set()

    for _, row in df.iterrows():
        author = row["display_name"]
        inst = row["current_affiliation"]
        size = max(5, row["number_of_works"])
        role = row["role"]
        color = {"PI": "darkblue", "PhD/ECR": "pink", "Researcher": "salmon"}.get(role, "gray")
        tooltip = f"{author}; {inst}; Works: {row['number_of_works']}; Role: {role}"

        net.add_node(author, label=author, shape="dot", size=size, title=tooltip, color=color)

        if pd.notna(inst):
            if inst not in added_institutions:
                net.add_node(inst, label=inst, shape="box", color="lightblue")
                added_institutions.add(inst)
            net.add_edge(author, inst)

    # --- Build co-authorship edges based on shared DOIs ---
    doi_to_authors = defaultdict(set)

    for _, row in df.iterrows():
        author = row["display_name"]
        if pd.isna(row["associated_dois"]):
            continue
        try:
            dois = ast.literal_eval(row["associated_dois"])
            for doi in set(d.strip().lower() for d in dois if isinstance(d, str) and d.strip()):
                doi_to_authors[doi].add(author)
        except (ValueError, SyntaxError):
            continue

    coauthor_counts = defaultdict(int)
    for authors in doi_to_authors.values():
        for a1, a2 in combinations(sorted(authors), 2):
            key = tuple(sorted((a1, a2)))
            coauthor_counts[key] += 1

    for (a1, a2), count in coauthor_counts.items():
        if a1 in author_names and a2 in author_names:
            net.add_edge(a1, a2, color="green", value=count, title=f"Co-authored {count} times")

    html_path = "/tmp/pyvis_graph.html"
    net.write_html(html_path)
    components.html(Path(html_path).read_text(encoding="utf-8"), height=800, width=1400, scrolling=False)

else:
    st.info("👈 Use the sidebar to set filters and generate the network.")
