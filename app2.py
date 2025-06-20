import streamlit as st
import pandas as pd
from pyvis.network import Network
from itertools import combinations
from collections import defaultdict
import streamlit.components.v1 as components
from pathlib import Path

# --- Inject JS to capture clicks and send them to Streamlit ---
def inject_click_event(html_str):
    injection = """
    <script type="text/javascript">
      function notifyStreamlit(label) {
        const streamlitFrame = window.parent;
        streamlitFrame.postMessage({ type: 'NODE_CLICK', label: label }, "*");
      }

      const interval = setInterval(() => {
        if (window.network && window.network.body) {
          clearInterval(interval);
          window.network.on("click", function (params) {
            if (params.nodes.length > 0) {
              const nodeId = params.nodes[0];
              const node = window.network.body.data.nodes.get(nodeId);
              notifyStreamlit(node.label);
            }
          });
        }
      }, 500);
    </script>
    """
    return html_str.replace("</body>", injection + "\n</body>")

# --- Sidebar: Upload CSV files ---
st.sidebar.title("\ud83d\udcc1 Upload Data")

researcher_file = st.sidebar.file_uploader("Upload researcher summary CSV", type="csv")
papers_file = st.sidebar.file_uploader("Upload author papers CSV", type="csv")

if not researcher_file:
    researcher_file = "data/european_researcher_summary.csv"
if not papers_file:
    papers_file = "data/european_author_papers.csv"

df = pd.read_csv(researcher_file)
papers_df = pd.read_csv(papers_file)

# --- Sidebar: Filters ---
available_countries = sorted(df["country_code"].dropna().unique())
select_all = st.sidebar.checkbox("\ud83c\udf0d Select all countries", value=True)

if select_all:
    selected_countries = st.sidebar.multiselect("Countries", available_countries, default=available_countries)
else:
    selected_countries = st.sidebar.multiselect("Countries", available_countries)

available_roles = ["PI", "PhD/ECR", "Researcher"]
selected_roles = st.sidebar.multiselect("\ud83e\uddea Filter by role", available_roles, default=available_roles)
top_n = st.sidebar.slider("\ud83d\udd1d Show top N researchers", min_value=10, max_value=200, value=50, step=10)

generate = st.sidebar.button("\ud83d\ude80 Generate Network")

st.title("\ud83d\udd2c European Researcher Network Explorer")

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

    author_names = {}
    institutions = df["most_recent_affiliation_name"].dropna().unique()
    for inst in institutions:
        net.add_node(inst, label=inst, shape="box", color="lightblue")

    for _, row in df.iterrows():
        author_id = row["author_id"]
        author = row["display_name"]
        inst = row["most_recent_affiliation_name"]
        size = max(5, row["number_of_works"])
        role = row["role"]
        color = {"PI": "darkblue", "PhD/ECR": "pink", "Researcher": "salmon"}.get(role, "gray")
        tooltip = f"{author}; {inst}<br>Works: {row['number_of_works']}; Role: {role}"

        author_names[author_id] = author
        net.add_node(author, label=author, shape="dot", size=size, title=tooltip, color=color)
        if inst:
            net.add_edge(author, inst)

    papers_df = papers_df[papers_df["standard_class"] == "Positive"]
    author_cols = ["first_author_id", "last_author_id", "corresponding_author_id"]
    papers_df[author_cols] = papers_df[author_cols].astype(str)

    coauthor_counts = defaultdict(int)
    for _, row in papers_df.iterrows():
        authors = {row[col] for col in author_cols if row[col] in author_names}
        for a1, a2 in combinations(sorted(authors), 2):
            key = tuple(sorted((author_names[a1], author_names[a2])))
            coauthor_counts[key] += 1

    for (a1, a2), count in coauthor_counts.items():
        net.add_edge(a1, a2, color="green", value=count, title=f"Co-authored {count} times")

    html_path = "/tmp/pyvis_graph.html"
    net.write_html(html_path)
    html_str = Path(html_path).read_text(encoding="utf-8")
    html_str = inject_click_event(html_str)

    st.markdown("""
        <style>
        iframe {
            display: block;
            width: 100vw !important;
            height: 100vh !important;
            border: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

    components.html(html_str, height=0, scrolling=False)

    # Setup JS event listener to receive clicked label from postMessage
    st.markdown("""
    <script>
    window.addEventListener("message", (event) => {
        const data = event.data;
        if (data.type === "NODE_CLICK") {
            const input = window.parent.document.querySelector("input[data-testid='stTextInput']");
            const nativeInput = input.querySelector("input");
            nativeInput.value = data.label;
            nativeInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    });
    </script>
    """, unsafe_allow_html=True)

    clicked_label = st.text_input("\ud83d\udcc8 Clicked Node")

    if clicked_label and clicked_label in df["display_name"].values:
        row = df[df["display_name"] == clicked_label].iloc[0]
        st.sidebar.markdown("### \ud83d\udc64 Selected Researcher")
        st.sidebar.markdown(f"""
**Name:** {row['display_name']}  
**Affiliation:** {row['most_recent_affiliation_name']}  
**Country:** {row['country_code']}  
**Role:** {row['role']}  
**Works:** {row['number_of_works']}  
**Active Since:** {row['active_since']}  
        """)

else:
    st.info("\ud83d\udc48 Use the sidebar to set filters and generate the network.")