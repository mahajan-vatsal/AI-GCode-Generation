# Laser_Control

## Overview
The `Laser_Control` module contains the low-level hardware control interface for the laser engraver.  
It handles serial communication with the laser’s controller, actuator movements via an ESP32, fan control through a RevPi ModIO, and execution of G-code commands.  

This module is the core driver that other components (GUI, OPC UA server, G-code generator) use to send commands to the engraver.

## Features
- **Serial Communication** with the laser engraver.
- **Actuator Control** (height and push) via WebSocket to ESP32.
- **Run G-code** from files or lists of commands.
- **File Management**: List and retrieve G-code files.
- **Pointer Laser Control** for positioning.
- **Fan Control** using RevPi ModIO.
- **Automated Card Insertion/Removal** sequences.
- **Dummy Mode** for testing without hardware.

## Files
- **`laser.py`** – Main control class `Laser` implementing all hardware operations.
- **`GcodeShared/`** – Shared directory for G-code files.

## Dependencies
- `pyserial` – Serial communication.
- `websocket-client` – ESP32 actuator control.
- `revpimodio2` – RevPi ModIO interface (only if not in dummy mode).
- Standard Python libraries: `threading`, `time`, `os`, `sys`.

## Class: `Laser`
### Constructor Parameters
```
Laser(
    port="/dev/ttyUSB2",
    baudrate=115200,
    timeout=1,
    gcode_dir="/gcode_shared/",
    esp_ip="192.168.157.20:81",
    dummy=False
)
```
- **`port`**: Serial port of the engraver.
- **`baudrate`**: Serial communication speed.
- **`timeout`**: Serial read timeout.
- **`gcode_dir`**: Path to directory containing G-code files.
- **`esp_ip`**: IP and port of ESP32 actuator (WebSocket).
- **`dummy`**: If `True`, enables simulation mode without hardware.

## Key Methods
| Method | Description |
|--------|-------------|
| `connect()` | Establish connection to the engraver and ESP32 actuator. |
| `connected()` | Returns `True` if the serial connection is open. |
| `esp_connected()` | Returns `True` if the ESP32 actuator is connected. |
| `send_command(command)` | Sends a single G-code command. |
| `run_file(filename)` | Executes all commands from a G-code file. |
| `run_code(codes)` | Executes a list of G-code commands. |
| `stop()` | Stops current execution. |
| `reference()` | Homes the machine (moves actuator up first). |
| `move_relativ(x, y)` | Moves head relative to current position. |
| `move_absolut(x, y, feed)` | Moves head to absolute coordinates. |
| `pointer(on)` | Turns pointer laser on/off for positioning. |
| `list_files()` | Returns a list of G-code files in `gcode_dir`. |
| `fan_control(onoff)` | Turns cooling fan on or off. |
| `push_card_in()` | Runs automated sequence to insert a card. |
| `push_card_out()` | Runs automated sequence to remove a card. |

## Example Usage
```
from Laser_Control.laser import Laser

# Initialize in dummy mode for testing
laser = Laser(dummy=True, gcode_dir="./Laser_Control/GcodeShared/")

# List available G-code files
print(laser.list_files())

# Run a G-code file
laser.run_file("example.gc")

# Move laser head
laser.move_absolut(100, 200, feed=5000)

# Stop current operation
laser.stop()
```

## Notes
- In **dummy mode**, hardware communication is simulated for development/testing.
- Ensure the correct **serial port** and **ESP32 IP** are set before running in real mode.
- The automated card insertion/removal sequences are hardcoded for a specific mechanical setup.
