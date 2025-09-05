# streamlit.py
# Run:  streamlit run streamlit.py
# This UI talks to your FastAPI (server_api.py).

import streamlit as st
import requests
import os

DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://api:8080")  # <— default to service name in compose

st.set_page_config(page_title="AI-GCode UI", page_icon="🛠️", layout="wide")

# --- Config ---
with st.sidebar:
    st.header("Connection")
    SERVER_URL = st.text_input(
        "Server API URL",
        value=DEFAULT_API_BASE,  # <— use env/default, not 127.0.0.1
        help="Your FastAPI (server_api.py) base URL",
        key="server_url_input",
    )
    st.caption(f"Resolved API base: {SERVER_URL}")
    st.divider()
    st.header("OPC UA")
    OLD_SERVER_ENDPOINT = st.text_input(
        "Old OPC UA endpoint",
        value="opc.tcp://127.0.0.1:4840/laser/",
        key="old_opcua_endpoint",
    )
    OLD_SERVER_NS = st.text_input(
        "Old OPC UA namespace",
        value="laser_module",
        key="old_opcua_ns",
    )
    NEW_SERVER_ENDPOINT = st.text_input(
        "New OPC UA endpoint",
        value="opc.tcp://127.0.0.1:4840/gcode",
        key="new_opcua_endpoint",
    )

st.title("AI-GCode — End-to-End UI")
st.caption("Upload → OCR/Visual → SVG → Preview → Rasterize → G-code → Preview → Download → Publish")

if "job_id" not in st.session_state:
    st.session_state.job_id = None

# --- Helpers ---
def api_post(path, **kwargs):
    url = f"{SERVER_URL}{path}"
    r = requests.post(url, **kwargs)
    if r.status_code >= 400:
        try:
            st.error(f"POST {path} → {r.status_code}: {r.json()}")
        except Exception:
            st.error(f"POST {path} → {r.status_code}: {r.text}")
        raise RuntimeError(f"POST {path} failed")
    return r

def api_get(path, **kwargs):
    url = f"{SERVER_URL}{path}"
    r = requests.get(url, **kwargs)
    if r.status_code >= 400:
        try:
            st.error(f"GET {path} → {r.status_code}: {r.json()}")
        except Exception:
            st.error(f"GET {path} → {r.status_code}: {r.text}")
        raise RuntimeError(f"GET {path} failed")
    return r

# --- 1) Upload & create job ---
st.header("1) Upload business card image")
upcol1, upcol2 = st.columns([3, 1])
with upcol1:
    file = st.file_uploader(
        "Choose an image",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        key="uploader",
    )
with upcol2:
    if st.button("Create Job", use_container_width=True, disabled=file is None, key="btn_create_job"):
        files = {"image": (file.name, file.getvalue(), file.type)}
        res = api_post("/jobs", files=files)
        data = res.json()
        st.session_state.job_id = data["job_id"]
        st.success(f"Job created: {st.session_state.job_id}")

if not st.session_state.job_id:
    st.stop()

st.info(f"Current Job: {st.session_state.job_id}")

# --- 2) OCR / Visual ---
st.header("2) Extract info (OCR) & Visual analysis")
col_ocr, col_vis = st.columns(2)
with col_ocr:
    if st.button("Run OCR", use_container_width=True, key="btn_run_ocr"):
        res = api_post(f"/node/{st.session_state.job_id}/ocr")
        st.json(res.json())
with col_vis:
    if st.button("Run Visual Analysis", use_container_width=True, key="btn_run_visual"):
        res = api_post(f"/node/{st.session_state.job_id}/visual")
        st.json(res.json())

# --- 3) SVG generation ---
st.header("3) SVG Generate & Preview")
gcol1, gcol2, gcol3 = st.columns([1, 1, 1])
with gcol1:
    if st.button("Generate SVG", use_container_width=True, key="btn_gen_svg"):
        res = api_post(f"/node/{st.session_state.job_id}/svg/generate")
        st.json(res.json())
with gcol2:
    if st.button("Preview SVG (PNG)", use_container_width=True, key="btn_preview_svg"):
        res = api_get(f"/node/{st.session_state.job_id}/svg/preview")
        st.image(res.content, caption="SVG Preview (Rasterized)")
with gcol3:
    if st.button("Download SVG", use_container_width=True, key="btn_download_svg"):
        res = api_get(f"/node/{st.session_state.job_id}/svg/file")
        st.download_button(
            "Save SVG",
            data=res.content,
            file_name="design.svg",
            mime="image/svg+xml",
            use_container_width=True,
            key="dl_svg_btn",
        )

# --- 4) Edit SVG ---
st.header("4) Edit SVG (optional)")

# Tools to map & inspect elements (duplicate controls allowed; keys must differ)
emap1, emap2, emap3 = st.columns([1, 1, 2])
with emap1:
    if st.button("Map elements now", use_container_width=True, key="btn_map_elements_edit"):
        res = api_post(f"/node/{st.session_state.job_id}/svg/map")
        st.json(res.json())
with emap2:
    if st.button("List elements", use_container_width=True, key="btn_list_elements_edit"):
        try:
            res = api_get(f"/node/{st.session_state.job_id}/svg/elements")
            st.json(res.json())
        except RuntimeError:
            st.warning("Elements not in state yet. Click 'Map elements now' first.")

# Choose editing mode
mode = st.radio(
    "Edit mode",
    ["Natural language (LLM)", "Raw commands"],
    horizontal=True,
    key="edit_mode_radio",
)

if mode == "Natural language (LLM)":
    instruction = st.text_area(
        "Describe your change (e.g., 'Move logo to top-right and add text tagline at x=10 y=8')",
        height=120,
        placeholder="Move logo to top-right; add_text tagline at x=10 y=8 text='Crafted by Vatsal' size=3.2 weight=bold",
        key="instruction_text",
    )
    if st.button("Submit Instruction", use_container_width=True, disabled=not instruction.strip(), key="btn_submit_instruction"):
        body = {"instruction": instruction.strip()}
        res = api_post(f"/node/{st.session_state.job_id}/svg/edit", json=body)
        st.success("Edit applied via LLM.")
        st.json(res.json())
        # Auto-preview updated SVG
        try:
            res_prev = api_get(f"/node/{st.session_state.job_id}/svg/preview")
            st.image(res_prev.content, caption="SVG Preview (after edit)")
        except RuntimeError:
            st.warning("Preview failed — check server logs.")

else:
    commands = st.text_area(
        "Raw commands (one per line)",
        height=150,
        placeholder="move_by logo_0 dx=3.5 dy=2\nresize image_1 to width=15 height=15\nadd_text tagline at x=10 y=8 text='Crafted by Vatsal' size=3",
        key="commands_text",
    )
    if st.button("Submit Commands", use_container_width=True, disabled=not commands.strip(), key="btn_submit_commands"):
        body = {"commands": commands.strip()}
        res = api_post(f"/node/{st.session_state.job_id}/svg/edit", json=body)
        st.success("Edit applied via commands.")
        st.json(res.json())
        # Auto-preview updated SVG
        try:
            res_prev = api_get(f"/node/{st.session_state.job_id}/svg/preview")
            st.image(res_prev.content, caption="SVG Preview (after edit)")
        except RuntimeError:
            st.warning("Preview failed — check server logs.")

# --- 5) Rasterize for engraving ---
st.header("5) Rasterize")
if st.button("Rasterize", use_container_width=True, key="btn_rasterize"):
    res = api_post(f"/node/{st.session_state.job_id}/rasterize")
    st.json(res.json())

# --- 6) G-code generate ---
st.header("6) Generate G-code")
gc1, gc2, gc3 = st.columns([1, 1, 2])
with gc1:
    g_rel = st.checkbox("Relative mode (G91)", value=False, key="chk_relative_mode")
with gc2:
    ax = st.number_input("Anchor X (mm)", value=0.0, step=0.1, key="num_anchor_x")
    ay = st.number_input("Anchor Y (mm)", value=0.0, step=0.1, key="num_anchor_y")
with gc3:
    if st.button("Generate G-code", use_container_width=True, key="btn_gen_gcode"):
        body = {"gcode_relative": g_rel, "gcode_anchor": [ax, ay]}
        res = api_post(f"/node/{st.session_state.job_id}/gcode/generate", json=body)
        st.json(res.json())

# --- 7) G-code preview & download ---
st.header("7) Download G-code")
prevcol, dlcol = st.columns(2)
#with prevcol:
    #if st.button("Preview Toolpath (PNG)", use_container_width=True, key="btn_preview_gcode"):
     #   res = api_get(f"/node/{st.session_state.job_id}/gcode/preview")
        #st.image(res.content, caption="G-code Toolpath Preview")
#       st.info("⚠️ G-code preview temporarily disabled due to Tkinter blocking issues.")
with dlcol:
    if st.button("Download G-code", use_container_width=True, key="btn_download_gcode"):
        res = api_get(f"/node/{st.session_state.job_id}/gcode/file")
        st.download_button(
            "Save .gcode",
            data=res.content,
            file_name="output.gcode",
            mime="text/plain",
            use_container_width=True,
            key="dl_gcode_btn",
        )

# --- 8) Publish (optional) ---
st.header("8) Publish to OPC UA (optional)")
pub1, pub2 = st.columns(2)
with pub1:
    if st.button("Publish to NEW GCode server", use_container_width=True, key="btn_publish_new"):
        body = {"endpoint": NEW_SERVER_ENDPOINT}
        res = api_post(f"/node/{st.session_state.job_id}/opcua/publish", json=body)
        st.success("Published to NEW OPC UA.")
        st.json(res.json())
with pub2:
    if st.button("Publish to OLD HMI server", use_container_width=True, key="btn_publish_old"):
        body = {"endpoint": OLD_SERVER_ENDPOINT, "namespace_uri": OLD_SERVER_NS}
        res = api_post(f"/node/{st.session_state.job_id}/bridge/opcua-old", json=body)
        st.success("Published to OLD OPC UA (HMI).")
        st.json(res.json())

st.divider()
st.caption("Tip: change the API URL in the sidebar if your server is remote.")
