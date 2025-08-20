from langgraph.graph import StateGraph
from agents.ocr_agent import ocr_info_extraction
from agents.visual_analysis_agent import visual_analysis_agent
from agents.svg_agent import generate_svg_from_layout
from agents.svg_preview_agent import svg_preview_node
from agents.rasterization import rasterization_node
from agents.gcode_agent import gcode_generation_node
from agents.gcodePreview_agent import gcode_preview_node
from agents.gcode_agent import gcode_generation_node
from graph.subgraph import build_svg_edit_subgraph
from langgraph.types import interrupt
from typing import TypedDict, Optional, List, Dict, Tuple
from dotenv import load_dotenv

load_dotenv()

# -------------------------
# State Type Definition
# -------------------------
class WorkflowState(TypedDict, total=False):
    image_path: str
    extracted_info: Dict[str, str]
    text_blocks: List[Dict[str, str]]
    qr_code: Optional[Dict]
    nfc_chip: Optional[Dict]
    logos: Optional[List[Dict]]
    icons: Optional[List[Dict]]
    layout_override: Optional[List[Dict]]
    svg_content: Optional[str]
    svg_path: Optional[str]
    png_path: Optional[str]      
    bw_path: Optional[str]       
    gcode_content: Optional[str]
    material_settings: Optional[Dict]
    choice: Optional[str]
    preview_count: Optional[int]
    svg_id_patched_path: Optional[str]  # Path to ID-patched SVG
    svg_elements: Optional[Dict] # List of SVG elements for editing
    edit_commands: Optional[str]  # Commands for editing SVG
    svg_version: int
    svg_history: List[str]
    gcode_relative: Optional[bool]
    gcode_anchor: Optional[Tuple[float, float]]

# -------------------------
# Node Definitions
# -------------------------
def ocr_node(state: WorkflowState) -> WorkflowState:
    if "image_path" not in state:
        raise ValueError("Missing 'image_path' in state.")
    image_path = state["image_path"]
    extracted_info = ocr_info_extraction.invoke(image_path)
    state["extracted_info"] = extracted_info
    return state

def visual_node(state: WorkflowState) -> WorkflowState:
    image_path = state["image_path"]
    visual_info = visual_analysis_agent.invoke(image_path, debug=True)
    state["text_blocks"] = visual_info["text_blocks"]
    state["qr_code"] = visual_info.get("qr_code")
    state["nfc_chip"] = visual_info.get("nfc_chip")
    state["logos"] = visual_info.get("logos")
    state["icons"] = visual_info.get("icons")
    return state

def svg_node(state: WorkflowState) -> WorkflowState:
    layout_override = state.get("layout_override", [])
    qr_code = state.get("qr_code", {})
    nfc_chip = state.get("nfc_chip", {})
    logos = state.get("logos", [])
    icons = state.get("icons", [])

    result = generate_svg_from_layout.invoke({
        "text_blocks": state["text_blocks"],
        "qr_code": qr_code if qr_code else {},
        "nfc_chip": nfc_chip if nfc_chip else {},
        "logos": logos if logos else [],
        "icons": icons if icons else [],
        "user_override": layout_override if layout_override else []
    })

    state["svg_content"] = result["svg_content"]
    state["svg_path"] = result["svg_path"]
    return state


def svg_handle_choice_node(state: WorkflowState) -> WorkflowState:
    # Ask user whether to edit or proceed
    choice = interrupt(
        {
            "message": "You can Preview the generated svg on the desktop. What would you like to do next with the SVG?",
            "options": [
                {"value": "edit", "label": "Edit SVG"},
                {"value": "proceed", "label": "Proceed to Rasterization"}
            ]
        }
    )

    # Store choice in state for conditional branching
    state["choice"] = choice
    return state


# -------------------------
# Subgraph Wrapper Node
# -------------------------
svg_edit_subgraph = build_svg_edit_subgraph()

def svg_edit_subgraph_node(state: WorkflowState) -> WorkflowState:
    sub_state = {
        "svg_path": state.get("svg_path"),
        "svg_content": state.get("svg_content"),
    }

    result = svg_edit_subgraph.invoke(sub_state)

    # Merge back relevant keys
    state["svg_path"] = result.get("svg_path", state.get("svg_path"))
    state["svg_content"] = result.get("svg_content", state.get("svg_content"))
    state["edit_commands"] = result.get("edit_commands")
    state["edit_instruction"] = result.get("edit_instruction")
    state["svg_elements"] = result.get("svg_elements")
    state["svg_id_patched_path"] = result.get("svg_id_patched_path", state.get("svg_id_patched_path"))

    return state

# -------------------------
# Build Main Graph
# -------------------------
def build_main_graph():
    builder = StateGraph(WorkflowState)

    builder.add_node("ocr_info_extraction", ocr_node)
    builder.add_node("visual_analysis", visual_node)
    builder.add_node("svg_generation", svg_node)
    builder.add_node("svg_preview_prompt", svg_preview_node)
    builder.add_node("svg_handle_choice", svg_handle_choice_node)
    builder.add_node("edit_svg_subgraph", svg_edit_subgraph_node)
    builder.add_node("rasterization", rasterization_node)
    builder.add_node("gcode_generation", gcode_generation_node)
    builder.add_node("gcode_preview", gcode_preview_node)

    builder.add_conditional_edges(
        "svg_handle_choice",
        lambda state: state["choice"],
        {
            "edit": "edit_svg_subgraph",
            "proceed": "rasterization"
        }
    )

    builder.add_edge("edit_svg_subgraph", "svg_preview_prompt")
    builder.set_entry_point("ocr_info_extraction")
    builder.add_edge("ocr_info_extraction", "visual_analysis")
    builder.add_edge("visual_analysis", "svg_generation")
    builder.add_edge("svg_generation", "svg_preview_prompt")
    builder.add_edge("svg_preview_prompt", "svg_handle_choice")
    builder.add_edge("rasterization", "gcode_generation")
    builder.add_edge("gcode_generation", "gcode_preview")
    builder.set_finish_point("gcode_preview")

    return builder.compile()

graph_app = build_main_graph()
