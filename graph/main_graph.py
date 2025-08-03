# 2. WorkflowState and Node Updates (main_graph.py)

from langgraph.graph import StateGraph
from agents.ocr_agent import ocr_info_extraction
from agents.visual_analysis_agent import visual_analysis_agent
#from agents.svg_agent import generate_svg_from_layout
#from agents.gcode_agent import generate_gcode_from_svg
from typing import TypedDict, Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()


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
    gcode_content: Optional[str]
    material_settings: Optional[Dict]

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

    result = generate_svg_from_layout.invoke({
        "text_blocks": state["text_blocks"],
        "qr_code": qr_code if qr_code else {},
        "user_override": layout_override if layout_override else []
    })

    state["svg_content"] = result["svg_content"]
    return state

def gcode_node(state: WorkflowState) -> WorkflowState:
    result = generate_gcode_from_svg.invoke({
        "svg_content": state["svg_content"],
        "material_settings": state.get("material_settings", {})
    })

    state["gcode_content"] = result.get("gcode_content", "")
    return state

def user_override_node(state: WorkflowState) -> WorkflowState:
    """
    Optional step where user can modify or inject new layout elements (e.g., move text, remove logo).
    """
    # This can be manually edited in LangGraph Studio UI
    state["layout_override"] = state.get("layout_override", [])  # Prepopulate or empty
    return state


def build_main_graph():
    builder = StateGraph(WorkflowState)

    builder.add_node("ocr_info_extraction", ocr_node)
    builder.add_node("visual_analysis", visual_node)
    builder.add_node("user_override", user_override_node)
    builder.add_node("svg_generation", svg_node)
    #builder.add_node("gcode_generation", gcode_node)

    builder.set_entry_point("ocr_info_extraction")
    builder.add_edge("ocr_info_extraction", "visual_analysis")
    builder.add_edge("visual_analysis", "user_override")
    builder.add_edge("user_override", "svg_generation")
    #builder.add_edge("svg_generation", "gcode_generation")
    builder.set_finish_point("svg_generation")

    graph = builder.compile()
    return graph


# Export for Studio
graph_app = build_main_graph()

"""

# Directory: agents/
# File: main_graph.py

from langgraph.graph import StateGraph
from typing import TypedDict, Optional, List, Dict

class WorkflowState(TypedDict, total=False):
    image_path: str
    extracted_info: Dict[str, str]

def ocr_node(state: WorkflowState) -> WorkflowState:
    print("OCR Node called!")
    state["extracted_info"] = {"name": "Test", "email": "test@example.com"}
    return state

def build_main_graph():
    builder = StateGraph(WorkflowState)
    builder.add_node("ocr_info_extraction", ocr_node)
    builder.set_entry_point("ocr_info_extraction")
    builder.set_finish_point("ocr_info_extraction")
    return builder.compile()

graph_app = build_main_graph()


"""