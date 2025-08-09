# AI G‑Code Generation

**Transform scanned business cards into laser‑ready G‑Code using AI‑powered vision and language models.**

This project orchestrates a pipeline that takes a picture of a business card and produces both an editable vector design (SVG) and machine‑ready G‑code for laser engraving or milling. It combines multiple cutting‑edge techniques, computer vision, OCR, large language models, vector graphics and CNC path planning, into a cohesive LangGraph workflow.

---

## 🚀 What It Does
- **Extract information** — The **ocr_agent** uses an advanced vision model (via Fireworks/OpenAI) to read the card and return structured JSON fields (name, title, contact details, conference info, etc.).
- **Detect layout elements** —The **visual_analysis_agent** calls a vision language model (Qwen2.5‑VL) to detect bounding boxes for all visual items (text, logos, QR code, NFC chip) and enriches them with sizes in millimetres.
- **Generate SVG design** — The **svg_agent** assembles an SVG from the detected text blocks, logos, icons and optional user overrides. It can embed QR codes and NFC icons and flips the Y‑axis to match millimetre coordinates.
- **Preview and edit** — Users can preview the card and optionally modify it. The **svg_preview_agent** launches a zoomable Tkinter window; the **svg_mapper_agent** maps semantic elements and gives them IDs; the **llm_svg_agent** uses a language model to turn free‑form instructions into edit commands; the **svg_editor_agent** applies those commands (move, delete, replace) to the SVG.
- **Rasterize and binarize** — The **rasterization** module converts the SVG into a high‑resolution PNG and then into a black‑and‑white image, ready for engraving.
- **Generate G‑code** — The **gcode_agent** reads the binarized image and produces a scanline G‑code program, including zig‑zag motion, laser on/off commands and proper feedrates
- **Preview G‑code** – The **gcode_preview_agent** parses G‑code, scales it to fit a canvas and draws the toolpath so you can visualise the engraving before running it.

The entire sequence is orchestrated via a LangGraph graph in **graph/main_graph.py**. Users can choose to edit the SVG or proceed directly to rasterization and G‑code generation.

---

## 📂 Repository Structure
| Directory/File                    | Contents/Role                                               |
| --------------------------------- | ----------------------------------------------------------- |
| `agents/ocr_agent.py`             | Business card OCR via Fireworks                             |
| `agents/visual_analysis_agent.py` | Layout detection and enrichment                             |
| `agents/svg_agent.py`             | SVG generation from layout                                  |
| `agents/svg_mapper_agent.py`      | Assigns IDs and maps SVG elements                           |
| `agents/llm_svg_agent.py`         | Generates edit commands from user instructions using an LLM |
| `agents/svg_editor_agent.py`      | Parses commands (move, delete, replace) and updates SVG     |
| `agents/rasterization.py`         | Converts SVG to PNG and to black‑and‑white                  |
| `agents/gcode_agent.py`           | Generates scanline G‑code from a bitmap                     |
| `agents/gcodePreview_agent.py`    | Previews G‑code toolpaths                                   |
| `graph/main_graph.py`             | Defines the primary LangGraph workflow                      |
| `graph/subgraph.py`               | Subgraph for interactive SVG editing                        |
| `langgraph.json`                  | LangGraph configuration for CLI/host                        |
| `requirements.txt`                | Python dependencies for this project                        |


---

## 📦 Installation
1. **Clone the repo** (or download the ZIP if using internal connectors):
```bash
git clone https://github.com/mahajan-vatsal/AI-GCode-Generation.git
```
2. **Set up Python** – This project requires Python ≥ 3.12. Create a virtual environment and install dependencies:
```bash
cd AI-GCode-Generation
python3 -m nenv env
source env/bin/activate
pip install -r requirements.txt
```
3. **API keys** – Create a **.env** file in the project root with the following keys:
```bash
# Fireworks (OpenAI) for OCR and layout detection
FIREWORKS_API_KEY=your_fireworks_key_here
# OpenRouter (Mistral) for generating SVG edit commands
OPENROUTER_API_KEY=your_openrouter_key_here
#Langgraph for defining the Workflow
LANGCHAIN_PROJECT=AI-GCode-Generator
export LANGCHAIN_API_KEY=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
export LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=AI-GCode-Generator
```
4. **Run the workflow** - Use the LangGraph API (installed via langgraph-api):
```bash
langgraph dev
```
5. **Output** - After completion you will find:
- **output.svg / output_edited.svg** – the generated vector business card.
- **output_edited.png** and **output_edited_bw.png** – rasterized versions used for engraving.
- **output_edited.gcode** – the final G‑code file ready for your CNC or laser engraver.



---

## 📊 LangGraph Flow
Below is the actual LangGraph pipeline used in this project:

![LangGraph Flow](langgraph_flow.png)

---

## 🚀 Example Workflow — From Card to Code

1. **📷 Upload Your Business Card**  
   Provide an image (`.jpg`, `.png`, or scanned PDF).  
   The system reads it in and preps for analysis.

2. **🔍 Layout & Element Detection**  
   **Visual Analysis Agent** finds logos, text blocks, QR codes, NFC chips.  
   Output: structured layout map.

3. **✏️ OCR & Semantic Mapping**  
   **OCR Agent** extracts text content.  
   **SVG Mapper Agent** maps items into meaningful IDs (e.g., `logo_top_left`, `name_center`).

4. **🖌️ AI-Powered SVG Design**  
   **SVG Agent** creates a vector business card design.  
   Logos are traced into vector paths for crisp engraving.

5. **🛠️ Intelligent Editing**  
   Ask the system: *“Move logo to top-right”* → instantly updates SVG via **LLM-SVG Agent**.

6. **🖼️ Rasterization & Binarization**  
   **Rasterization Agent** converts SVG to PNG.  
   **Binarization** ensures clean black/white separation for engraving.

7. **🖋️ Laser-Ready G-Code**  
   **G-Code Agent** generates optimized toolpaths. 
   Supports raster engraving for smooth fills.

8. **👀 Preview & Export**  
   **G-Code Preview Agent** renders the final toolpaths before you hit the laser.
