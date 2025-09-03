# Generate_Gcode

## Purpose
This module is responsible for generating laser engraving G-code files based on text input, predefined templates, and character vector files. It supports multiple engraving layouts ("variants") and allows offset adjustments.

## Main Features
- **Multiple Variants**: Predefined engraving layouts (`hs`, `blank`, `hs-simple`, `zdin`, `icps2025`, etc.).
- **Template-based G-code generation**: Loads base G-code from template files.
- **Dynamic text insertion**: Places text strings at specific coordinates with different font sizes.
- **Font-based character shapes**: Reads `.gc` files for each character from the `Letters/` directory.
- **Coordinate and size calculation**: Determines bounding box offsets for each character.
- **Output cleanup**: Adds necessary initialization and removes redundant commands.

## Directory Structure
```
Generate_Gcode/
├── Generate_Gcode.py     # Main generation logic
├── Letters/              # Character vector G-code files
└── Templets/             # Base engraving templates
```

## Usage
```python
from Generate_Gcode import Generate_Gcode

# Initialize
ggen = Generate_Gcode(variant="hs", offset=[4, 86])

# Data to engrave
info = {
    "variant": "hs",
    "name": "John Doe",
    "job_title": "Engineer",
    "phone": "123456789"
}

# Generate G-code
ggen.generate_gcode(info)

# Retrieve G-code
gcode = ggen.get_gcode()
print(gcode)
```

## Variants Overview
- **hs / blank** – Standard layouts with multiple fields.
- **hs-simple** – Minimal layout with fewer fields.
- **zdin** – layout for ZDIN.
- **icps2025 / icps2025V2 / icps2025Blank / icps2025Logo** – Custom layouts for ICPS 2025 event badges.

## Requirements
- Python 3.x
- Standard library (`os`, `re`)
- Template and letter `.gc` files in `Templets/` and `Letters/`
