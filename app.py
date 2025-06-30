import streamlit as st
import pandas as pd
from pyvis.network import Network
from itertools import combinations
from collections import defaultdict
import streamlit.components.v1 as components
from pathlib import Path

# --- Sidebar: Upload CSV file ---
st.sidebar.title("📁 Upload Data")

researcher_file = st.sidebar.file_uploader("Upload researcher summary CSV", type="csv")
if not researcher_file:
    researcher_file = "data/Contact_list_deeptech_researchers.csv"

df = pd.read_csv(researcher_file)

# --- Sidebar: Filters ---
available_countries = sorted(df["country_code"].dropna().unique())
select_all = st.sidebar.checkbox("🌍 Select all countries", value=True)

if select_all:
    selected_countries = st.sidebar.multiselect("Countries", available_countries, default=available_countries)
else:
    selected_countries = st.sidebar.multiselect("Countries", available_countries)

available_roles = ["PI", "PhD/ECR", "Researcher"]
selected_roles = st.sidebar.multiselect("Filter by role", available_roles, default=available_roles)
top_n = st.sidebar.slider("🔝 Show top N researchers", min_value=10, max_value=len(df), value=10, step=1)

generate = st.sidebar.button("🚀 Generate Network")

st.title("🔬 European Researcher Network Explorer")

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

    # Build co-authorship edges from 'associated_dois'
    coauthor_counts = defaultdict(int)
    for _, row in df.iterrows():
        author = row["display_name"]
        if pd.isna(row["associated_dois"]):
            continue
        coauthors = row["associated_dois"].split(";")
        coauthors = [a.strip() for a in coauthors if a.strip() in author_names and a.strip() != author]
        for coauthor in coauthors:
            key = tuple(sorted((author, coauthor)))
            coauthor_counts[key] += 1

    for (a1, a2), count in coauthor_counts.items():
        net.add_edge(a1, a2, color="green", value=count, title=f"Co-authored {count} times")

    html_path = "/tmp/pyvis_graph.html"
    net.write_html(html_path)
    components.html(Path(html_path).read_text(encoding="utf-8"), height=800, scrolling=False)

else:
    st.info("Use the sidebar to set filters and generate the network.")