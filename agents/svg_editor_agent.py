import xml.etree.ElementTree as ET
import re
from pathlib import Path
import os


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)
NS = {"svg": SVG_NS, "xlink": XLINK_NS}


# Accept move_by with optional dy (defaults to 0)
MOVE_BY_REGEX = r"move_by\s+(\w+)\s+dx=([-+]?\d*\.?\d+)(?:\s+dy=([-+]?\d*\.?\d+))?"
# Also accept absolute move
MOVE_REGEX = r"move\s+(\w+)\s+to\s+x=([-+]?\d*\.?\d+)\s+y=([-+]?\d*\.?\d+)"
REPLACE_REGEX = r"replace\s+(\w+)\s+(?:with\s+)?['\"](.+?)['\"]"
DELETE_REGEX = r"delete\s+(\w+)"
_VERSION_RE = re.compile(r"^(?P<stem>.*?)(?:_v(?P<n>\d{3}))?\.svg$", re.I)

def parse_commands(commands_str: str):
    commands = []
    for line in commands_str.strip().splitlines():
        line = line.strip("`- ").strip()
        if not line:
            continue

        m = re.match(MOVE_BY_REGEX, line, re.I)
        if m:
            dx = float(m.group(2))
            dy = float(m.group(3)) if m.group(3) is not None else 0.0  # ✅ default dy
            commands.append({"action": "move_by", "id": m.group(1), "dx": dx, "dy": dy})
            continue

        m = re.match(MOVE_REGEX, line, re.I)
        if m:
            commands.append({"action": "move", "id": m.group(1), "x": float(m.group(2)), "y": float(m.group(3))})
            continue

        m = re.match(DELETE_REGEX, line, re.I)
        if m:
            commands.append({"action": "delete", "id": m.group(1)})
            continue

        m = re.match(REPLACE_REGEX, line, re.I)
        if m:
            commands.append({"action": "replace", "id": m.group(1), "content": m.group(2)})
            continue

        print(f"⚠️ Warning: Could not parse command line: {line}")
    return commands

def apply_edit_commands_to_svg(svg_input_path, commands_str, svg_output_path):
    commands = parse_commands(commands_str)
    if not commands:
        raise ValueError(f"No commands recognized by parser. Raw:\n{commands_str}")

    tree = ET.parse(svg_input_path)   # will work if path exists
    root = tree.getroot()

    def first_float(val):
        if val is None or val == "":
            return 0.0
        return float(str(val).split()[0])

    for cmd in commands:
        elem_id = cmd["id"]
        elem = root.find(f".//*[@id='{elem_id}']", NS)
        if elem is None:
            print(f"⚠️ Element with id '{elem_id}' not found.")
            continue

        tag = elem.tag.split("}")[-1]

        if cmd["action"] == "move_by":
            if tag in ["text", "image"]:
                cur_x = first_float(elem.get("x"))
                cur_y = first_float(elem.get("y"))
                elem.set("x", str(cur_x + cmd["dx"]))
                elem.set("y", str(cur_y + cmd["dy"]))
            else:
                prev = (elem.get("transform") or "").strip()
                elem.set("transform", f"{prev} translate({cmd['dx']} {cmd['dy']})".strip())
            print(f"✅ Moved '{elem_id}' by dx={cmd['dx']}, dy={cmd['dy']}")

        elif cmd["action"] == "move":
            if tag in ["text", "image"]:
                elem.set("x", str(cmd["x"]))
                elem.set("y", str(cmd["y"]))
                print(f"✅ Moved '{elem_id}' to x={cmd['x']}, y={cmd['y']}")
            else:
                prev = (elem.get("transform") or "").strip()
                # best-effort: absolute becomes a translate
                elem.set("transform", f"{prev} translate({cmd['x']} {cmd['y']})".strip())
                print(f"✅ Applied translate({cmd['x']} {cmd['y']}) to '{elem_id}'")

        elif cmd["action"] == "delete":
            parent = root.find(f".//*[@id='{elem_id}']/..", NS)
            if parent is not None:
                parent.remove(elem)
                print(f"✅ Deleted element '{elem_id}'")
            else:
                print(f"⚠️ Could not find parent to delete element '{elem_id}'")

        elif cmd["action"] == "replace":
            if tag == "text":
                elem.text = cmd["content"]
                print(f"✅ Replaced text in '{elem_id}' with '{cmd['content']}'")
            elif tag == "image":
                elem.set(f"{{{XLINK_NS}}}href", cmd["content"])
                print(f"✅ Replaced image href in '{elem_id}' with '{cmd['content']}'")
            else:
                print(f"⚠️ Replace not supported for tag '{tag}'")

    tree.write(svg_output_path, encoding="utf-8", xml_declaration=True)
    print(f"\n✅ Edited SVG saved as: {svg_output_path}")

def extract_valid_commands(command_str):
    valid = []
    for line in command_str.strip().splitlines():
        line = line.strip("`- ").strip()
        if line.lower().startswith(("move_by", "move", "delete", "replace")):
            valid.append(line)
    return "\n".join(valid)

def next_version_path(current_svg_path: str) -> str:
    p = Path(current_svg_path)
    m = _VERSION_RE.match(p.name)
    if not m:
        # Fallback: append v002
        return str(p.with_name(p.stem + "_v002.svg"))
    stem = m.group("stem") or p.stem
    n = int(m.group("n")) + 1 if m.group("n") else 2  # treat unversioned as v001 → next = v002
    return str(p.with_name(f"{stem}_v{n:03d}.svg"))

def svg_editor_node(state):
    print("State keys:", state.keys())
    print("svg_id_patched_path:", state.get("svg_id_patched_path"))
    print("svg_path:", state.get("svg_path"))
    print("edit_commands:", state.get("edit_commands"))

    # Prefer patched file, but fall back if missing
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

    # ✅ NEW: write to a next versioned file based on the CURRENT (non-patched) svg_path
    # Always use the *real* current svg_path as the base for the version name
    base_for_version = state.get("svg_path") or input_path
    output_path = next_version_path(base_for_version)

    apply_edit_commands_to_svg(input_path, commands, output_path)

    with open(output_path, "r", encoding="utf-8") as f:
        state["svg_content"] = f.read()

    # ✅ Point the workflow to the new version going forward
    state["svg_path"] = output_path
    state["svg_history"] = (state.get("svg_history") or []) + [state["svg_path"]]
    state["svg_version"] = (state.get("svg_version") or 1) + 1

    # Clear any stale patched path; svg_mapper will generate a fresh one each time
    state["svg_id_patched_path"] = None
    return state
