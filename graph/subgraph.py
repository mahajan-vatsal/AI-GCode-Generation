from langgraph.graph import StateGraph
from langgraph.types import interrupt
from agents.svg_mapper_agent import parse_svg_semantic
from agents.llm_svg_agent import llm_svg_node
from agents.svg_editor_agent import svg_editor_node
from typing import TypedDict, Optional, Dict

class SvgEditState(TypedDict, total=False):
    svg_path: str
    svg_content: Optional[str]
    svg_id_patched_path: Optional[str]
    svg_elements: Optional[Dict]
    edit_instruction: Optional[str]
    edit_commands: Optional[str]

def svg_mapper_node(state: SvgEditState) -> SvgEditState:
    if not state.get("svg_path"):
        raise ValueError("Missing 'svg_path' in state.")

    # ✅ Write the patched file and get the real path back
    elements, patched_path = parse_svg_semantic(
        state["svg_path"], 
        save_id_patched_svg=True
    )
    state["svg_elements"] = elements
    state["svg_id_patched_path"] = patched_path or state["svg_path"]
    return state

def svg_instruction_node(state: SvgEditState) -> SvgEditState:
    user_instruction = interrupt({
        "message": "What changes would you like to make to the SVG?",
        "options": None
    })
    state["edit_instruction"] = user_instruction
    return state




def build_svg_edit_subgraph():
    builder = StateGraph(SvgEditState)
    builder.add_node("svg_mapper", svg_mapper_node)
    builder.add_node("svg_instruction", svg_instruction_node)
    builder.add_node("llm_svg", llm_svg_node)
    builder.add_node("svg_editor", svg_editor_node)

    builder.set_entry_point("svg_mapper")
    builder.add_edge("svg_mapper", "svg_instruction")
    builder.add_edge("svg_instruction", "llm_svg")
    builder.add_edge("llm_svg", "svg_editor")
    builder.set_finish_point("svg_editor")

    return builder.compile()
