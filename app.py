import streamlit as st
import pandas as pd

from scholarScrapperScript import (
    setup_proxy,
    get_publications,
    build_html,
    profile_ids as default_profile_ids,
)

st.title("Scholar Publication Scraper")

# --- Proxy setup (once per session) ---
@st.cache_resource
def init_proxy():
    with st.spinner("Setting up proxy..."):
        setup_proxy()

init_proxy()

# --- Profile ID input ---
st.subheader("Author Profile IDs")
ids_input = st.text_area(
    "One Google Scholar profile ID per line",
    value="\n".join(default_profile_ids),
    height=120,
)

profile_ids = [pid.strip() for pid in ids_input.strip().splitlines() if pid.strip()]

# --- Fetch button ---
if st.button("Fetch Publications", type="primary"):
    if not profile_ids:
        st.warning("Enter at least one profile ID.")
    else:
        with st.status("Fetching publications...", expanded=True) as status:
            messages = st.empty()
            log_lines = []

            def on_progress(msg):
                log_lines.append(msg)
                messages.markdown("\n\n".join(f"`{line}`" for line in log_lines[-10:]))

            publications = get_publications(profile_ids, progress_callback=on_progress)
            status.update(label=f"Done — {len(publications)} unique publications fetched.", state="complete")

        st.session_state["publications"] = publications

# --- Editable table ---
if "publications" in st.session_state:
    st.subheader("Publications")

    df = pd.DataFrame(st.session_state["publications"])
    edited_df = st.data_editor(
        df,
        column_config={
            "title":    st.column_config.TextColumn("Title", width="large"),
            "year":     st.column_config.TextColumn("Year", width="small"),
            "journal":  st.column_config.TextColumn("Journal / Conference", width="medium"),
            "authors":  st.column_config.TextColumn("Authors", width="large"),
            "citations":st.column_config.NumberColumn("Citations", width="small"),
            "url":      st.column_config.LinkColumn("Link", width="small"),
        },
        use_container_width=True,
        num_rows="dynamic",
        key="pub_editor",
    )

    # --- Export ---
    html = build_html(edited_df.to_dict("records"))
    st.download_button(
        label="Export HTML",
        data=html,
        file_name="publications.html",
        mime="text/html",
    )
