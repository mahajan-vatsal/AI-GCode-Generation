# server_api.py
# REST API wrapper around your LangGraph agents, node-by-node.
# Run:  uvicorn server_api:app --host 0.0.0.0 --port 8080

from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import shutil
import uuid
import json
from fastapi import Path as _PathParam 
# --- add near other imports ---
from graph.subgraph import build_svg_edit_subgraph
from agents.svg_mapper_agent import svg_semantic_mapper_node
from agents.llm_svg_agent import llm_svg_node
from agents.svg_editor_agent import svg_editor_node


# ==== Import your existing agents ====
from agents.ocr_agent import ocr_info_extraction
from agents.visual_analysis_agent import visual_analysis_agent
from agents.svg_agent import generate_svg_from_layout
from agents.rasterization import rasterization_node  # returns {'png_path', 'bw_path'}
from agents.gcode_agent import gcode_generation_node
# We won't spawn Tkinter previews; we render images/files and serve them.
from client.client_hmi import upload_gcode_to_opcua

# --- ADDED ---
from opcua import Client, ua  # freeopcua client to talk to the old asyncua server

# ---- Helpers for previews without GUI ----
from PIL import Image, ImageDraw
import re
import math

# ============ Server config / storage ============
ROOT = Path("./runtime")
ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AI-GCode Node API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)

# Simple in-memory job store (swap with Redis later if needed)
JOBS: Dict[str, Dict] = {}

# ============ Models ============
class EditBody(BaseModel):
    # Either direct structured commands or natural language to be handled by your LLM editor (if you wire it)
    commands: Optional[str] = None
    instruction: Optional[str] = None

class GcodeOptions(BaseModel):
    gcode_relative: Optional[bool] = False
    gcode_anchor: Optional[Tuple[float, float]] = (0.0, 0.0)

class OPCUASettings(BaseModel):
    endpoint: Optional[str] = "opc.tcp://127.0.0.1:4840/gcode"

# --- ADDED ---
class OldServerSettings(BaseModel):
    endpoint: str = "opc.tcp://127.0.0.1:4840/laser/"
    namespace_uri: str = "laser_module"

# ============ Utilities ============
def new_job() -> str:
    jid = uuid.uuid4().hex[:12]
    job_dir = ROOT / jid
    job_dir.mkdir(parents=True, exist_ok=True)
    JOBS[jid] = {
        "job_id": jid,
        "dir": str(job_dir),
        # pipeline state mirrors your WorkflowState keys
        "state": {
            "svg_version": 0,
            "svg_history": [],
        }
    }
    return jid

def get_job(job_id: str) -> Dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    return job

def save_upload(upload: UploadFile, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return str(dest)

def render_gcode_preview_to_png(gcode_path: Path, out_png: Path, scale: float = 2.0):
    """
    Minimal headless G-code preview: parses G0/G1 X Y moves and draws lines.
    """
    points = []
    x = y = 0.0
    with gcode_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("(") or s.startswith(";"):
                continue
            # Parse coordinates
            parts = dict(re.findall(r'([XY])([-+]?\d+(?:\.\d+)?)', s))
            if "X" in parts or "Y" in parts:
                nx = float(parts.get("X", x))
                ny = float(parts.get("Y", y))
                points.append(((x, y), (nx, ny), s.startswith("G1")))
                x, y = nx, ny

    # Compute bounds
    xs = [p[0][0] for p in points] + [p[1][0] for p in points]
    ys = [p[0][1] for p in points] + [p[1][1] for p in points]
    if not xs or not ys:
        # empty
        img = Image.new("RGB", (600, 400), "white")
        img.save(out_png)
        return str(out_png)

    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    pad = 10
    w = int((maxx - minx) * scale) + 2 * pad
    h = int((maxy - miny) * scale) + 2 * pad
    w = max(w, 200)
    h = max(h, 200)

    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    # Draw
    for (x1,y1),(x2,y2), is_cut in points:
        # map to image space (Y grows down)
        ix1 = int((x1 - minx) * scale) + pad
        iy1 = int((y1 - miny) * scale) + pad
        ix2 = int((x2 - minx) * scale) + pad
        iy2 = int((y2 - miny) * scale) + pad
        draw.line([(ix1,iy1),(ix2,iy2)], fill=(0,0,0) if is_cut else (180,180,180), width=1)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return str(out_png)

@app.get("/node/{job_id}/svg/file")
def node_svg_file(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    svg = st.get("svg_path")
    if not svg:
        raise HTTPException(404, "No SVG for this job. Run /node/{job_id}/svg/generate first.")
    return FileResponse(svg, media_type="image/svg+xml", filename=Path(svg).name)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/node/{job_id}/gcode/file")
def node_gcode_file(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    g = st.get("gcode_path")
    if not g:
        raise HTTPException(404, "No G-code for this job. Run /node/{job_id}/gcode/generate first.")
    return FileResponse(g, media_type="text/plain", filename=Path(g).name)

EDIT_SUBGRAPH = build_svg_edit_subgraph()




# --- ADDED ---
def push_to_old_opcua(gcode_path: str,
                      endpoint: str = "opc.tcp://127.0.0.1:4840/laser/",
                      ns_uri: str = "laser_module") -> Dict:
    """
    Push the generated file to the old OPC UA server via put_gcode(name, data).
    Returns a small info dict including a snapshot of list_of_files if available.
    """
    p = Path(gcode_path)
    if not p.exists():
        raise FileNotFoundError(f"{gcode_path} not found")
    blob = p.read_bytes()

    c = Client(endpoint)
    c.connect()
    try:
        ns = c.get_namespace_index(ns_uri)
        root = c.get_root_node()
        gcode_obj = root.get_child([f"0:Objects", f"{ns}:gcode"])
        put = gcode_obj.get_child([f"{ns}:put_gcode"])

        rc = gcode_obj.call_method(
            put,
            ua.Variant(p.name, ua.VariantType.String),
            ua.Variant(blob, ua.VariantType.ByteString),
        )

        # Optional quick verification: read 'status/list_of_files'
        files = None
        try:
            status_obj = root.get_child([f"0:Objects", f"{ns}:status"])
            lof_node = status_obj.get_child([f"{ns}:list_of_files"])
            files = lof_node.get_value()
        except Exception:
            pass

        return {
            "return_code": int(rc) if rc is not None else -1,
            "listed_after_upload": (p.name in files) if isinstance(files, list) else None,
            "files_snapshot": files,
        }
    finally:
        c.disconnect()

# ============ Endpoints ============

@app.post("/jobs")
def create_job(image: UploadFile = File(...)):
    jid = new_job()
    job = get_job(jid)
    job_dir = Path(job["dir"])
    img_path = job_dir / image.filename
    save_upload(image, img_path)
    # prime state
    job["state"]["image_path"] = str(img_path)
    return {"job_id": jid, "image_path": str(img_path)}

@app.get("/jobs/{job_id}")
def get_state(job_id: str):
    job = get_job(job_id)
    return job

# 1) OCR extraction node
@app.post("/node/{job_id}/ocr")
def node_ocr(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    if "image_path" not in st:
        raise HTTPException(400, "image_path missing; create job with an image first")
    st["extracted_info"] = ocr_info_extraction.invoke(st["image_path"])
    return {"extracted_info": st["extracted_info"]}

# 2) Visual analysis node
@app.post("/node/{job_id}/visual")
def node_visual(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    if "image_path" not in st:
        raise HTTPException(400, "image_path missing")
    vis = visual_analysis_agent.invoke(st["image_path"], debug=True)
    st["text_blocks"] = vis.get("text_blocks", [])
    st["qr_code"] = vis.get("qr_code")
    st["nfc_chip"] = vis.get("nfc_chip")
    st["logos"] = vis.get("logos")
    st["icons"] = vis.get("icons")
    return {
        "text_blocks": st["text_blocks"],
        "qr_code": st["qr_code"],
        "nfc_chip": st["nfc_chip"],
        "logos": st["logos"],
        "icons": st["icons"],
    }

# 3) SVG generation node
@app.post("/node/{job_id}/svg/generate")
def node_svg_generate(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    result = generate_svg_from_layout.invoke({
        "text_blocks": st.get("text_blocks", []),
        "qr_code": st.get("qr_code") or {},
        "nfc_chip": st.get("nfc_chip") or {},
        "logos": st.get("logos") or [],
        "icons": st.get("icons") or [],
        "user_override": st.get("layout_override") or [],
    })
    st["svg_content"] = result["svg_content"]
    st["svg_path"] = result["svg_path"]
    st["svg_history"] = st.get("svg_history", []) + [result["svg_path"]]
    st["svg_version"] = st.get("svg_version", 0) + 1
    return {"svg_path": st["svg_path"], "svg_version": st["svg_version"]}

# 4) SVG preview (PNG) – renders and returns a file the client can display
@app.get("/node/{job_id}/svg/preview")
def node_svg_preview(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    if not st.get("svg_path"):
        raise HTTPException(400, "No SVG yet; run /svg/generate first")
    # Use your rasterization node to produce PNG (non-bw)
    # We mimic a state call
    tmp_state = {"svg_path": st["svg_path"]}
    res = rasterization_node(tmp_state)  # expects {'png_path', 'bw_path'}
    st["png_path"] = res.get("png_path")
    st["bw_path"] = res.get("bw_path")
    if not st.get("png_path"):
        raise HTTPException(500, "Rasterization did not produce png_path")
    return FileResponse(st["png_path"])

# 5) Decision: proceed vs edit — client just posts its choice (front-end logic)
@app.post("/node/{job_id}/decide")
def node_decide(job_id: str, action: str = Body(..., embed=True)):
    if action not in ("edit", "proceed"):
        raise HTTPException(400, "action must be 'edit' or 'proceed'")
    return {"ok": True, "action": action}

# 6) SVG edit – natural language and/or structured commands, runs your full edit subgraph
@app.post("/node/{job_id}/svg/edit")
def node_svg_edit(job_id: str, body: EditBody):
    job = get_job(job_id)
    st = job["state"]

    if not (st.get("svg_path") or st.get("svg_content")):
        raise HTTPException(400, "No SVG in state; run /node/{job_id}/svg/generate first")

    # 1) Ensure we have mapped elements + id-patched file
    svg_semantic_mapper_node(st)  # mutates: svg_elements, svg_id_patched_path

    # 2) Determine commands
    if body.instruction and body.instruction.strip():
        st["edit_instruction"] = body.instruction.strip()
        llm_svg_node(st)  # mutates: edit_commands
    elif body.commands and body.commands.strip():
        st["edit_commands"] = body.commands.strip()
    else:
        raise HTTPException(400, "Provide either 'instruction' or 'commands'.")

    # 3) Apply edits (writes a new versioned SVG, updates svg_path, clears patched)
    svg_editor_node(st)

    # 4) (Optional but recommended) Remap fresh edited SVG for next round
    try:
        svg_semantic_mapper_node(st)
    except Exception:
        pass

    return {
        "ok": True,
        "svg_version": st.get("svg_version"),
        "svg_path": st.get("svg_path"),
        "svg_id_patched_path": st.get("svg_id_patched_path"),
        "num_elements": len(st.get("svg_elements") or []),
        "applied_commands": st.get("edit_commands"),
        "applied_instruction": st.get("edit_instruction"),
    }

@app.post("/node/{job_id}/svg/map")
def node_svg_map(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    if not st.get("svg_path"):
        raise HTTPException(400, "No SVG path; run /svg/generate first")
    try:
        svg_semantic_mapper_node(st)  # mutates state
    except Exception as e:
        raise HTTPException(500, f"SVG mapping failed: {e}")
    # Prefer ID-patched file for downstream steps
    patched = st.get("svg_id_patched_path")
    if patched:
        st["svg_path"] = patched
    return {
        "ok": True,
        "count": len(st.get("svg_elements") or []),
        "svg_path": st.get("svg_path"),
        "svg_id_patched_path": st.get("svg_id_patched_path"),
    }

# Inspect current SVG elements for UI-side pickers (IDs, types, text, etc.)
@app.get("/node/{job_id}/svg/elements")
def node_svg_elements(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    elems = st.get("svg_elements")
    if elems is None:
        raise HTTPException(404, "No svg_elements in state. Run /svg/generate and then /svg/edit at least once.")
    return {"count": len(elems), "elements": elems}

# Get the latest on-disk SVG (prefer id-patched if present)
@app.get("/node/{job_id}/svg/latest")
def node_svg_latest(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    path = st.get("svg_id_patched_path") or st.get("svg_path")
    if not path:
        raise HTTPException(404, "No SVG file yet. Run /svg/generate.")
    return FileResponse(path, media_type="image/svg+xml", filename=Path(path).name)


# 7) Rasterize to BW (for engraving)
@app.post("/node/{job_id}/rasterize")
def node_rasterize(job_id: str):
    job = get_job(job_id)
    st = job["state"]
    if not st.get("svg_path"):
        raise HTTPException(400, "svg_path missing; run /svg/generate first")
    res = rasterization_node({"svg_path": st["svg_path"]})
    st["png_path"] = res.get("png_path")
    st["bw_path"] = res.get("bw_path")
    return {"png_path": st["png_path"], "bw_path": st["bw_path"]}

# 8) G-code generate
@app.post("/node/{job_id}/gcode/generate")
def node_gcode_generate(job_id: str, opts: GcodeOptions = Body(default=GcodeOptions())):
    job = get_job(job_id)
    st = job["state"]
    if not st.get("bw_path"):
        raise HTTPException(400, "bw_path missing; run /rasterize first")

    # feed options into state for gcode node
    st["gcode_relative"] = bool(opts.gcode_relative)
    st["gcode_anchor"] = tuple(opts.gcode_anchor or (0.0, 0.0))

    out_state = gcode_generation_node(st)  # should return gcode_content and/or gcode_path
    st.update(out_state)

    # Ensure we have gcode content
    gcode_text = st.get("gcode_content")
    # Ensure we have a path
    gpath = st.get("gcode_path")
    if not gpath:
        # fallback next to bw image
        gpath = st["bw_path"].replace("_bw.png", ".gcode")
        st["gcode_path"] = gpath

    # If the file does not exist but we have content, write it.
    try:
        if gcode_text and (not Path(gpath).exists()):
            Path(gpath).parent.mkdir(parents=True, exist_ok=True)
            Path(gpath).write_text(gcode_text, encoding="utf-8")
    except Exception as e:
        raise HTTPException(500, f"Failed to write G-code to '{gpath}': {e}")

    # If still no file, error with a helpful message
    if not Path(gpath).exists():
        raise HTTPException(
            500,
            f"G-code file '{gpath}' not found and no gcode_content to write. "
            "Check gcode_generation_node output."
        )

    return {"gcode_path": st["gcode_path"]}

# 9) G-code preview image (no GUI)
@app.get("/node/{job_id}/gcode/preview")
def node_gcode_preview(job_id: str):
    job = get_job(job_id)
    st = job["state"]

    gpath = st.get("gcode_path")
    gtext = st.get("gcode_content")

    if not gpath and not gtext:
        raise HTTPException(400, "No G-code; run /gcode/generate first")

    # If we have content but no file (or the file has been removed), materialize it
    if (not gpath) or (gpath and not Path(gpath).exists()):
        if not gtext:
            raise HTTPException(500, "gcode_path missing or not found on disk, and no gcode_content in state.")
        # write a temp file inside the job dir
        job_dir = Path(job["dir"])
        job_dir.mkdir(parents=True, exist_ok=True)
        gpath = str(job_dir / "preview_tmp.gcode")
        try:
            Path(gpath).write_text(gtext, encoding="utf-8")
            st["gcode_path"] = gpath  # keep state coherent
        except Exception as e:
            raise HTTPException(500, f"Failed to write temporary G-code for preview: {e}")

    out_png = Path(job["dir"]) / "gcode_preview.png"
    try:
        render_gcode_preview_to_png(Path(gpath), out_png)
    except Exception as e:
        raise HTTPException(500, f"G-code preview render failed: {e}")

    if not out_png.exists():
        raise HTTPException(500, "Preview PNG was not created.")

    return FileResponse(str(out_png))


# 10) Publish to OPC UA (your newer publish flow)
@app.post("/node/{job_id}/opcua/publish")
def node_opcua_publish(job_id: str, settings: OPCUASettings = Body(default=OPCUASettings())):
    job = get_job(job_id)
    st = job["state"]
    if not st.get("gcode_path"):
        raise HTTPException(400, "No G-code; run /gcode/generate first")
    upload_gcode_to_opcua(st["gcode_path"], settings.endpoint or "opc.tcp://127.0.0.1:4840/gcode")
    return {"ok": True, "published": Path(st["gcode_path"]).name, "endpoint": settings.endpoint}

# --- ADDED ---
# 11) Bridge: push generated file directly into the OLD OPC UA server used by HMI
@app.post("/node/{job_id}/bridge/opcua-old")
def node_bridge_opcua_old(job_id: str, settings: OldServerSettings = Body(default=OldServerSettings())):
    job = get_job(job_id)
    st = job["state"]
    if not st.get("gcode_path"):
        raise HTTPException(400, "No G-code; run /gcode/generate first")
    info = push_to_old_opcua(st["gcode_path"], settings.endpoint, settings.namespace_uri)
    return {"ok": info.get("return_code", -1) == 0, "detail": info}

""""
curl -F "image=@samples/business_card3.png" http://127.0.0.1:8080/jobs  
curl -X POST "http://127.0.0.1:8080/node/${JOB}/ocr"
curl -X POST "http://127.0.0.1:8080/node/${JOB}/visual"
open "http://127.0.0.1:8080/node/${JOB}/svg/preview"
curl -X POST http://127.0.0.1:8080/node/${JOB}/gcode/generate \
  -H "Content-Type: application/json" \
  -d '{"gcode_relative": true, "gcode_anchor": [4.0, 86.0]}'
curl -X POST "http://127.0.0.1:8080/node/${JOB}/svg/generate"
curl -X POST "http://127.0.0.1:8080/node/${JOB}/rasterize"   
curl -X POST http://127.0.0.1:8080/node/${JOB}/gcode/generate \
  -H "Content-Type: application/json" \
  -d '{"gcode_relative": true, "gcode_anchor": [4.0, 86.0]}'
open "http://127.0.0.1:8080/node/${JOB}/gcode/preview"
curl -X POST http://127.0.0.1:8080/node/$JOB/bridge/opcua-old \
  -H "Content-Type: application/json" \
  -d '{"endpoint":"opc.tcp://127.0.0.1:4840/laser/","namespace_uri":"laser_module"}'

curl -X POST http://127.0.0.1:8080/node/$JOB/bridge/opcua-old \
  -H "Content-Type: application/json" \
  -d '{"endpoint":"opc.tcp://192.168.157.213:4840/laser/","namespace_uri":"laser_module"}'

"""
