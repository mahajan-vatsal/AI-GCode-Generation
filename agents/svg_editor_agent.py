import xml.etree.ElementTree as ET
import re
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)
NS = {"svg": SVG_NS, "xlink": XLINK_NS}

# Regex for command parsing
REPLACE_REGEX = r"replace\s+(\w+)\s+with\s+['\"](.+?)['\"]"
MOVE_REGEX = r"move\s+(\w+)\s+to\s+x=([\d.]+)\s+y=([\d.]+)"
DELETE_REGEX = r"delete\s+(\w+)"

def parse_commands(commands_str):
    commands = []
    for line in commands_str.strip().splitlines():
        line = line.strip("`- ").strip()
        if not line:
            continue

        m = re.match(MOVE_REGEX, line, re.I)
        if m:
            commands.append({
                "action": "move",
                "id": m.group(1),
                "x": float(m.group(2)),
                "y": float(m.group(3)),
            })
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
    tree = ET.parse(svg_input_path)
    root = tree.getroot()
    commands = parse_commands(commands_str)

    for cmd in commands:
        elem_id = cmd["id"]
        # Search any SVG element with the given ID directly (no <g> required)
        elem = root.find(f".//*[@id='{elem_id}']", NS)

        if elem is None:
            print(f"⚠️ Element with id '{elem_id}' not found.")
            continue

        tag = elem.tag.split("}")[-1]

        if cmd["action"] == "move":
            if tag in ["text", "image"]:
                elem.set("x", str(cmd["x"]))
                elem.set("y", str(cmd["y"]))
                print(f"✅ Moved '{elem_id}' to x={cmd['x']}, y={cmd['y']}")
            else:
                print(f"⚠️ Cannot move element of type '{tag}'.")

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
    """Filter out non-command lines and markdown formatting."""
    valid_commands = []
    for line in command_str.strip().splitlines():
        line = line.strip("`- ").strip()
        if line.lower().startswith(("move", "delete", "replace")):
            valid_commands.append(line)
    return "\n".join(valid_commands)

def svg_editor_node(state):
    print("State keys:", state.keys())
    print("svg_id_patched_path:", state.get("svg_id_patched_path"))
    print("svg_path:", state.get("svg_path"))
    print("edit_commands:", state.get("edit_commands"))
    
    input_path = state.get("svg_id_patched_path") or state.get("svg_path")
    if not input_path:
        raise ValueError("Missing 'svg_id_patched_path' or 'svg_path' in state.")
    
    output_path = "output_edited.svg"
    
    commands = state.get("edit_commands")
    if not commands:
        raise ValueError("Missing 'edit_commands' in state.")
    
    apply_edit_commands_to_svg(input_path, commands, output_path)
    
    with open(output_path, "r", encoding="utf-8") as f:
        state["svg_content"] = f.read()
    state["svg_path"] = output_path
    
    return state
