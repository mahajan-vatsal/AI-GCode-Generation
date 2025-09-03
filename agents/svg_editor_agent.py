import xml.etree.ElementTree as ET
import re
from pathlib import Path
import os
import base64
import mimetypes

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)
NS = {"svg": SVG_NS, "xlink": XLINK_NS}

# Keep CANVAS_HEIGHT consistent with mapper (bottom-left origin for API)
CANVAS_HEIGHT = 54.0  # mm

def to_svg_y(y_bottom_left: float) -> float:
    """Convert bottom-left y to SVG top-left y."""
    return CANVAS_HEIGHT - y_bottom_left

def dy_to_svg(dy_bottom_left: float) -> float:
    """Convert bottom-left dy to SVG dy (sign flip)."""
    return -dy_bottom_left

# Allow typical XML id characters: letters, digits, _, -, :, .
ID = r'(?:["\']?([A-Za-z_][A-Za-z0-9_\-:.]*)["\']?)'

# Accept move_by with optional dy (defaults to 0)
MOVE_BY_REGEX = rf"move_by\s+{ID}\s+dx=([-+]?\d*\.?\d+)(?:\s+dy=([-+]?\d*\.?\d+))?"
# Absolute move
MOVE_REGEX    = rf"move\s+{ID}\s+to\s+x=([-+]?\d*\.?\d+)\s+y=([-+]?\d*\.?\d+)"
# Absolute resize (in mm)
RESIZE_REGEX  = rf"resize\s+{ID}\s+to\s+width=([-+]?\d*\.?\d+)\s+height=([-+]?\d*\.?\d+)"
# Relative scale (uniform or non-uniform)
SCALE_BY_UNI  = rf"scale_by\s+{ID}\s+s=([-+]?\d*\.?\d+)"
SCALE_BY_BI   = rf"scale_by\s+{ID}\s+sx=([-+]?\d*\.?\d+)\s+sy=([-+]?\d*\.?\d+)"
REPLACE_REGEX = rf"replace\s+{ID}\s+(?:with\s+)?['\"](.+?)['\"]"
DELETE_REGEX  = rf"delete\s+{ID}"

# NEW: add commands
ADD_TEXT_REGEX  = rf"add_text\s+{ID}\s+at\s+x=([-+]?\d*\.?\d+)\s+y=([-+]?\d*\.?\d+)\s+text=['\"](.+?)['\"](?:\s+size=([-+]?\d*\.?\d+))?(?:\s+family=['\"](.+?)['\"])?(?:\s+weight=(normal|bold))?(?:\s+anchor=(start|middle|end))?"
ADD_IMAGE_REGEX = rf"add_image\s+{ID}\s+at\s+x=([-+]?\d*\.?\d+)\s+y=([-+]?\d*\.?\d+)\s+width=([-+]?\d*\.?\d+)\s+height=([-+]?\d*\.?\d+)\s+src=['\"](.+?)['\"](?:\s+role=(logo|icon|qr|nfc|image))?(?:\s+name=['\"](.+?)['\"])?"
ADD_LOGO_REGEX  = rf"add_logo\s+{ID}\s+at\s+x=([-+]?\d*\.?\d+)\s+y=([-+]?\d*\.?\d+)\s+width=([-+]?\d*\.?\d+)\s+height=([-+]?\d*\.?\d+)\s+src=['\"](.+?)['\"]"

_VERSION_RE   = re.compile(r"^(?P<stem>.*?)(?:_v(?P<n>\d{3}))?\.svg$", re.I)

# -------- Asset resolver (existing) --------
ASSET_SEARCH_DIRS = [
    ".", "assets", "assets/logos", "assets/icons", "assets/nfc_templates"
]
ASSET_EXTS = [".png", ".svg", ".jpg", ".jpeg", ".webp"]

def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        if path.suffix.lower() == ".svg":
            mime = "image/svg+xml"
        elif path.suffix.lower() in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif path.suffix.lower() == ".png":
            mime = "image/png"
        elif path.suffix.lower() == ".webp":
            mime = "image/webp"
        else:
            mime = "application/octet-stream"
    return mime

def _find_asset_path(token: str) -> Path | None:
    cand = Path(token)
    if cand.suffix:
        if cand.is_file():
            return cand
        for d in ASSET_SEARCH_DIRS:
            p = Path(d) / cand
            if p.is_file():
                return p
    else:
        for d in ASSET_SEARCH_DIRS:
            for ext in ASSET_EXTS:
                p = Path(d) / f"{token}{ext}"
                if p.is_file():
                    return p
    return None

def _to_data_uri(path: Path) -> str:
    mime = _guess_mime(path)
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def _resolve_image_href(token: str) -> str:
    t = (token or "").strip()
    if t.startswith("data:") or t.startswith("http://") or t.startswith("https://"):
        return t
    p = _find_asset_path(t)
    if p:
        try:
            return _to_data_uri(p)
        except Exception as e:
            print(f"⚠️ Failed to embed asset '{p}': {e}. Using raw token.")
    return t
# -------- END asset resolver --------

def parse_commands(commands_str: str):
    commands = []
    for line in commands_str.strip().splitlines():
        line = line.strip("`- ").strip()
        if not line:
            continue

        m = re.match(MOVE_BY_REGEX, line, re.I)
        if m:
            dx = float(m.group(2))
            dy = float(m.group(3)) if m.group(3) is not None else 0.0
            commands.append({"action": "move_by", "id": m.group(1), "dx": dx, "dy": dy})
            continue

        m = re.match(MOVE_REGEX, line, re.I)
        if m:
            commands.append({"action": "move", "id": m.group(1), "x": float(m.group(2)), "y": float(m.group(3))})
            continue

        m = re.match(RESIZE_REGEX, line, re.I)
        if m:
            commands.append({"action": "resize", "id": m.group(1), "width": float(m.group(2)), "height": float(m.group(3))})
            continue

        m = re.match(SCALE_BY_UNI, line, re.I)
        if m:
            s = float(m.group(2))
            commands.append({"action": "scale_by", "id": m.group(1), "sx": s, "sy": s})
            continue

        m = re.match(SCALE_BY_BI, line, re.I)
        if m:
            commands.append({"action": "scale_by", "id": m.group(1), "sx": float(m.group(2)), "sy": float(m.group(3))})
            continue

        m = re.match(DELETE_REGEX, line, re.I)
        if m:
            commands.append({"action": "delete", "id": m.group(1)})
            continue

        m = re.match(REPLACE_REGEX, line, re.I)
        if m:
            commands.append({"action": "replace", "id": m.group(1), "content": m.group(2)})
            continue

        # NEW: add_text
        m = re.match(ADD_TEXT_REGEX, line, re.I)
        if m:
            commands.append({
                "action": "add_text",
                "id": m.group(1),
                "x": float(m.group(2)),
                "y": float(m.group(3)),
                "text": m.group(4),
                "size": float(m.group(5)) if m.group(5) else None,
                "family": m.group(6) if m.group(6) else None,
                "weight": (m.group(7) or "normal") if m.group(7) else "normal",
                "anchor": (m.group(8) or "start") if m.group(8) else "start",
            })
            continue

        # NEW: add_image
        m = re.match(ADD_IMAGE_REGEX, line, re.I)
        if m:
            commands.append({
                "action": "add_image",
                "id": m.group(1),
                "x": float(m.group(2)),
                "y": float(m.group(3)),
                "width": float(m.group(4)),
                "height": float(m.group(5)),
                "src": m.group(6),
                "role": (m.group(7) or "image") if m.group(7) else "image",
                "name": m.group(8) if m.group(8) else None,
            })
            continue

        # NEW: add_logo (sugar over add_image with role=logo)
        m = re.match(ADD_LOGO_REGEX, line, re.I)
        if m:
            commands.append({
                "action": "add_image",
                "id": m.group(1),
                "x": float(m.group(2)),
                "y": float(m.group(3)),
                "width": float(m.group(4)),
                "height": float(m.group(5)),
                "src": m.group(6),
                "role": "logo",
                "name": None,
            })
            continue

        print(f"⚠️ Warning: Could not parse command line: {line}")
    return commands

# ---- additive safety: avoid delete+replace conflict on same id
def normalize_commands(commands):
    ids_with_replace = {c["id"] for c in commands if c["action"] == "replace"}
    if not ids_with_replace:
        return commands
    normalized = []
    for c in commands:
        if c["action"] == "delete" and c["id"] in ids_with_replace:
            print(f"ℹ️ Skipping delete for '{c['id']}' because a replace is present in this batch.")
            continue
        normalized.append(c)
    return normalized

def _first_float(val):
    if val is None or val == "":
        return 0.0
    return float(str(val).split()[0])

def _ensure_unique_id(root, desired_id: str) -> str:
    """If desired_id exists, append _2, _3, ... to make it unique."""
    if not desired_id:
        desired_id = "elem"
    candidate = desired_id
    i = 2
    while root.find(f".//*[@id='{candidate}']") is not None:
        candidate = f"{desired_id}_{i}"
        i += 1
    return candidate

def apply_edit_commands_to_svg(svg_input_path, commands_str, svg_output_path):
    commands = parse_commands(commands_str)
    if not commands:
        raise ValueError(f"No commands recognized by parser. Raw:\n{commands_str}")

    commands = normalize_commands(commands)

    tree = ET.parse(svg_input_path)
    root = tree.getroot()

    for cmd in commands:
        action = cmd["action"]

        # ------- ADD TEXT -------
        if action == "add_text":
            new_id = _ensure_unique_id(root, cmd["id"])
            text_el = ET.Element(f"{{{SVG_NS}}}text")
            text_el.set("id", new_id)
            text_el.set("x", str(cmd["x"]))
            text_el.set("y", str(to_svg_y(cmd["y"])))
            # Defaults; optional overrides
            size = cmd.get("size") if cmd.get("size") is not None else 3.0
            family = cmd.get("family") or "Arial"
            weight = cmd.get("weight") or "normal"
            anchor = cmd.get("anchor") or "start"
            text_el.set("font-size", str(size))
            text_el.set("font-family", family)
            text_el.set("font-weight", weight)
            text_el.set("text-anchor", anchor)
            text_el.set("dominant-baseline", "text-before-edge")
            text_el.set("fill", "black")
            text_el.set("data-role", "text")
            text_el.text = cmd["text"]
            root.append(text_el)
            print(f"✅ Added text '{new_id}' at ({cmd['x']}, {cmd['y']})")

            continue  # next command

        # ------- ADD IMAGE / LOGO -------
        if action == "add_image":
            new_id = _ensure_unique_id(root, cmd["id"])
            href_val = _resolve_image_href(cmd["src"])
            img_el = ET.Element(f"{{{SVG_NS}}}image")
            img_el.set("id", new_id)
            img_el.set("x", str(cmd["x"]))
            # Consistent with current editor 'move' semantics
            img_el.set("y", str(to_svg_y(cmd["y"])))
            img_el.set("width", str(cmd["width"]))
            img_el.set("height", str(cmd["height"]))
            role = cmd.get("role") or "image"
            img_el.set("data-role", role)
            # Set data-name if we can resolve an asset file (helps mapper show correct name)
            p = _find_asset_path(cmd["src"])
            if p:
                img_el.set("data-name", p.name)
            # Set both href forms for compatibility
            img_el.set(f"{{{XLINK_NS}}}href", href_val)
            img_el.set("href", href_val)
            root.append(img_el)
            print(f"✅ Added {role} '{new_id}' at ({cmd['x']}, {cmd['y']}) size=({cmd['width']}x{cmd['height']})")

            continue  # next command

        # ------- EXISTING ACTIONS ON EXISTING ELEMENTS -------
        elem_id = cmd.get("id")
        if not elem_id:
            print("⚠️ Command missing 'id'.")
            continue

        elem = root.find(f".//*[@id='{elem_id}']")
        if elem is None:
            print(f"⚠️ Element with id '{elem_id}' not found.")
            continue

        tag = elem.tag.split("}")[-1]

        if action == "move_by":
            if tag in ["text", "image"]:
                cur_x = _first_float(elem.get("x"))
                cur_y = _first_float(elem.get("y"))
                new_x = cur_x + cmd["dx"]
                new_y = cur_y + dy_to_svg(cmd["dy"])
                elem.set("x", str(new_x))
                elem.set("y", str(new_y))
            else:
                prev = (elem.get("transform") or "").strip()
                dx = cmd["dx"]
                dy = dy_to_svg(cmd["dy"])
                elem.set("transform", f"{prev} translate({dx} {dy})".strip())
            print(f"✅ Moved '{elem_id}' by dx={cmd['dx']}, dy={cmd['dy']} (bottom-left dy)")

        elif action == "move":
            if tag in ["text", "image"]:
                elem.set("x", str(cmd["x"]))
                elem.set("y", str(to_svg_y(cmd["y"])))
                print(f"✅ Moved '{elem_id}' to x={cmd['x']}, y={cmd['y']} (bottom-left)")
            else:
                prev = (elem.get("transform") or "").strip()
                elem.set("transform", f"{prev} translate({cmd['x']} {to_svg_y(cmd['y'])})".strip())
                print(f"✅ Applied translate({cmd['x']} {to_svg_y(cmd['y'])}) to '{elem_id}' (best-effort)")

        elif action == "resize":
            w = cmd["width"]
            h = cmd["height"]
            if tag == "image":
                elem.set("width", str(w))
                elem.set("height", str(h))
                print(f"✅ Resized image '{elem_id}' to width={w}, height={h}")
            elif tag == "g":
                resized = False
                for child in list(elem):
                    ctag = child.tag.split("}")[-1]
                    if ctag in ("image", "rect"):
                        child.set("width", str(w))
                        child.set("height", str(h))
                        resized = True
                if resized:
                    print(f"✅ Resized group '{elem_id}' children to width={w}, height={h}")
                else:
                    print(f"⚠️ Resize for group '{elem_id}' had no resizable children")
            else:
                print(f"⚠️ Resize not supported for tag '{tag}' (id='{elem_id}')")

        elif action == "scale_by":
            sx = cmd["sx"]
            sy = cmd["sy"]
            if tag == "image":
                cur_w = _first_float(elem.get("width"))
                cur_h = _first_float(elem.get("height"))
                elem.set("width", str(cur_w * sx))
                elem.set("height", str(cur_h * sy))
                print(f"✅ Scaled image '{elem_id}' by sx={sx}, sy={sy}")
            elif tag == "g":
                prev = (elem.get("transform") or "").strip()
                elem.set("transform", f"{prev} scale({sx} {sy})".strip())
                print(f"✅ Applied scale({sx} {sy}) to group '{elem_id}'")
            else:
                print(f"⚠️ scale_by not supported for tag '{tag}' (id='{elem_id}')")

        elif action == "delete":
            parent = root.find(f".//*[@id='{elem_id}']/..")
            if parent is not None:
                parent.remove(elem)
                print(f"✅ Deleted element '{elem_id}'")
            else:
                print(f"⚠️ Could not find parent to delete element '{elem_id}'")

        elif action == "replace":
            content = cmd["content"]
            if tag == "image":
                href_val = _resolve_image_href(content)
                elem.set(f"{{{XLINK_NS}}}href", href_val)
                elem.set("href", href_val)  # keep both for broad viewer compatibility
                # Also (re)store a friendly name if we can resolve a local asset
                p = _find_asset_path(content)
                if p:
                    elem.set("data-name", p.name)
                print(f"✅ Replaced image href in '{elem_id}' with resolved asset '{content}'")
            elif tag == "g":
                img_child = elem.find(".//{http://www.w3.org/2000/svg}image")
                if img_child is not None:
                    href_val = _resolve_image_href(content)
                    img_child.set(f"{{{XLINK_NS}}}href", href_val)
                    img_child.set("href", href_val)
                    p = _find_asset_path(content)
                    if p:
                        img_child.set("data-name", p.name)
                        elem.set("data-name", p.name)
                    print(f"✅ Replaced image inside group '{elem_id}' with '{content}'")
                else:
                    print(f"⚠️ Replace on group '{elem_id}' failed: no <image> child found")
            elif tag == "text":
                elem.text = content
                print(f"✅ Replaced text in '{elem_id}' with '{content}'")
            else:
                print(f"⚠️ Replace not supported for tag '{tag}'")

    tree.write(svg_output_path, encoding="utf-8", xml_declaration=True)
    print(f"\n✅ Edited SVG saved as: {svg_output_path}")

def extract_valid_commands(command_str):
    valid = []
    for line in command_str.strip().splitlines():
        line = line.strip("`- ").strip()
        if line.lower().startswith((
            "move_by","move","delete","replace","resize","scale_by",
            "add_text","add_image","add_logo"
        )):
            valid.append(line)
    return "\n".join(valid)

def next_version_path(current_svg_path: str) -> str:
    p = Path(current_svg_path)
    m = _VERSION_RE.match(p.name)
    if not m:
        return str(p.with_name(p.stem + "_v002.svg"))
    stem = m.group("stem") or p.stem
    n = int(m.group("n")) + 1 if m.group("n") else 2
    return str(p.with_name(f"{stem}_v{n:03d}.svg"))

def svg_editor_node(state):
    print("State keys:", state.keys())
    print("svg_id_patched_path:", state.get("svg_id_patched_path"))
    print("svg_path:", state.get("svg_path"))
    print("edit_commands:", state.get("edit_commands"))

    input_path = state.get("svg_id_patched_path") or state.get("svg_path")
    if not input_path:
        raise ValueError("Missing 'svg_id_patched_path' or 'svg_path' in state.")
    if not os.path.exists(input_path):
        print(f"⚠️ Patched SVG not found at {input_path}; falling back to original svg_path.")
        input_path = state.get("svg_path")
    if not input_path or not os.path.exists(input_path):
        raise FileNotFoundError(f"SVG not found at {input_path}")

    commands = state.get("edit_commands")
    if not commands:
        raise ValueError("Missing 'edit_commands' in state.")

    commands = extract_valid_commands(commands)
    if not commands.strip():
        raise ValueError("No valid edit commands parsed from LLM output.")

    base_for_version = state.get("svg_path") or input_path
    output_path = next_version_path(base_for_version)

    apply_edit_commands_to_svg(input_path, commands, output_path)

    with open(output_path, "r", encoding="utf-8") as f:
        state["svg_content"] = f.read()

    state["svg_path"] = output_path
    state["svg_history"] = (state.get("svg_history") or []) + [state["svg_path"]]
    state["svg_version"] = (state.get("svg_version") or 1) + 1
    state["svg_id_patched_path"] = None
    return state



#add_text tagline at x=3 y=6 text='Innovation for everyone' size=3.2