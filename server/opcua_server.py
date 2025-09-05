# old_server.py  (your existing file, with minimal additions)

import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio

from asyncua import Server, ua
from asyncua.common.methods import uamethod

from Laser_Control.laser import Laser
from orders import Orders
from Generate_Gcode.Generate_Gcode import Generate_Gcode

# --- ADDED ---
# (No extra imports needed; we reuse 'os' and existing Laser instance)

@uamethod
def reference(_) -> int:
    return laser.reference()

@uamethod
def send_command(_, command: str) -> int:
    return laser.send_command(command)

@uamethod
def run_file(_, filename: str) -> int:
    return laser.run_file(filename)

@uamethod
def get_gcode(_, filename: str) -> str:
    return laser.get_gcode(filename)

@uamethod
def run_code(_, codes: str) -> int:
    return laser.run_code(codes.split("\n"))

@uamethod
def generate_gcode(_, variant, title, name, division, job_title, phone, fax, mail):
    generate.generate_gcode(
        {
            "variant": variant,
            "title": title,
            "name": name,
            "division": division,
            "job_title": job_title,
            "phone": phone,
            "fax": fax,
            "mail": mail,
        }
    )

@uamethod
def get_generated_gcode(_):
    return generate.get_gcode()

@uamethod
def run_generated_gcode(_):
    return laser.run_code(generate.get_gcode().split("\n"))

@uamethod
def stop(_):
    return laser.stop()

@uamethod
def pointer(_, on: bool) -> int:
    return laser.pointer(on)

@uamethod
def fan_control(_, on: bool) -> int:
    return laser.fan_control(on)

@uamethod
def move_actuator_hight(_, angle: int = 0):
    return laser.move_actuator_hight(angle)

@uamethod
def put_file(_, filename: str, content: bytes) -> bool:
    """
    Store a G-code file into the laser's gcode directory so HMI can see it.
    """
    try:
        # Reuse the same directory Laser() is using
        target_dir = Path(laser._gcode_dir)  # laser is your global Laser() object
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / filename).write_bytes(content)
        return True
    except Exception as e:
        print("put_file failed:", e)
        return False

@uamethod
def move_actuator_push(_, angle: int = 0):
    return laser.move_actuator_push(angle)

@uamethod
def move_relativ(_, xval: int = 0, yval: int = 0) -> int:
    return laser.move_relativ(xval, yval)

@uamethod
def move_absolut(_, xval: int = 0, yval: int = 0, feed: int = 5000) -> int:
    return laser.move_absolut(xval, yval, feed)

@uamethod
def add_new_order(_, material, variant, name, title, phone, mail):
    return orders.add_new_order(material, variant, name, title, phone, mail)

@uamethod
def mark_done(_, order_number):
    return orders.mark_done(order_number)

@uamethod
def get_order_status(_, order_number):
    return orders.get_order_status(order_number)

@uamethod
def set_card_offset(_, x: int, y: int) -> None:
    generate.set_offset(x,y)

@uamethod
def connect(_):
    laser.connect()

@uamethod
def push_card_in(_):
    laser.push_card_in()

@uamethod
def push_card_out(_):
    laser.push_card_out()

# --- ADDED ---
@uamethod
def put_gcode(_, name: str, data: bytes) -> int:
    """
    Store a G-code file under laser._gcode_dir so it shows up in list_of_files.
    Returns 0 on success, -1 on failure.
    """
    try:
        # sanitize name (no paths) and ensure .gcode extension
        base = os.path.basename(name)
        if not base.endswith(".gcode"):
            base = base + ".gcode"

        dest = os.path.join(laser._gcode_dir, base)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)

        print(f"[put_gcode] wrote {len(data)} bytes to {dest}")
        return 0
    except Exception as e:
        print("[put_gcode] error:", e)
        return -1

async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/laser/")
#192.168.157.213/laser_module
    uri = "laser_module"
    idx = await server.register_namespace(uri)

    status = await server.nodes.objects.add_object(idx, "status")
    gcode = await server.nodes.objects.add_object(idx, "gcode")
    control = await server.nodes.objects.add_object(idx, "control")
    move = await server.nodes.objects.add_object(idx, "move")
    order = await server.nodes.objects.add_object(idx, "orders")

    is_connected = await status.add_variable(idx, "is_connected", False)
    is_mcu_connected = await status.add_variable(idx, "is_mcu_connected", False)
    is_running = await status.add_variable(idx, "is_running", False)
    list_of_files = await gcode.add_variable(idx, "list_of_files", [""])
    progress = await status.add_variable(idx, "progress", 0)

    next_order = await order.add_variable(idx, "next_order", [""])
    todo_list = await order.add_variable(idx, "todo_list", [""])
    done_list = await order.add_variable(idx, "done_list", [""])
    count_todo = await order.add_variable(idx, "count_todo", 0)
    count_done = await order.add_variable(idx, "count_done", 0)

    await control.add_method(
        ua.NodeId("reference", idx),
        ua.QualifiedName("reference", idx),
        reference,
        [],
        [ua.VariantType.Int64],
    )

    await control.add_method(
        ua.NodeId("send_command", idx),
        ua.QualifiedName("send_command", idx),
        send_command,
        [ua.VariantType.String],
        [ua.VariantType.Int64],
    )

    await control.add_method(
        ua.NodeId("set_card_offset", idx),
        ua.QualifiedName("set_card_offset", idx),
        set_card_offset,
        [ua.VariantType.Int64, ua.VariantType.Int64],
        [],
    )

    await gcode.add_method(
        ua.NodeId("run_file", idx),
        ua.QualifiedName("run_file", idx),
        run_file,
        [ua.VariantType.String],
        [ua.VariantType.Int64],
    )

    await gcode.add_method(
        ua.NodeId("get_gcode", idx),
        ua.QualifiedName("get_gcode", idx),
        get_gcode,
        [ua.VariantType.String],
        [ua.VariantType.String],
    )

    await gcode.add_method(
        ua.NodeId("run_code", idx),
        ua.QualifiedName("run_code", idx),
        run_code,
        [ua.VariantType.String],
        [ua.VariantType.Int64],
    )

    await gcode.add_method(
        ua.NodeId("generate_gcode", idx),
        ua.QualifiedName("generate_gcode", idx),
        generate_gcode,
        [
            ua.Argument(" Variant", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Title", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Name", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Division", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Job Title", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Phone", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Fax", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Mail", ua.NodeId(ua.ObjectIds.String), -1),
        ],
    )

    await control.add_method(
        ua.NodeId("connect", idx),
        ua.QualifiedName("connect", idx),
        connect,
    )

    await gcode.add_method(
        ua.NodeId("get_generated_gcode", idx),
        ua.QualifiedName("get_generated_gcode", idx),
        get_generated_gcode,
        [],
        [ua.VariantType.String],
    )

    await gcode.add_method(
        ua.NodeId("run_generated_gcode", idx),
        ua.QualifiedName("run_generated_gcode", idx),
        run_generated_gcode,
        [],
        [ua.VariantType.Int64],
    )

    await control.add_method(
        ua.NodeId("stop", idx),
        ua.QualifiedName("stop", idx),
        stop,
    )

    await control.add_method(
        ua.NodeId("pointer", idx),
        ua.QualifiedName("pointer", idx),
        pointer,
        [ua.VariantType.Boolean],
        [ua.VariantType.Int64],
    )

    await control.add_method(
        ua.NodeId("fan_control", idx),
        ua.QualifiedName("fan_control", idx),
        fan_control,
        [ua.VariantType.Boolean],
        [ua.VariantType.Int64],
    )

    await move.add_method(
        ua.NodeId("move_actuator_hight", idx),
        ua.QualifiedName("move_actuator_hight", idx),
        move_actuator_hight,
        [ua.VariantType.Int64],
        [ua.VariantType.Int64],
    )

    await move.add_method(
        ua.NodeId("move_actuator_push", idx),
        ua.QualifiedName("move_actuator_push", idx),
        move_actuator_push,
        [ua.VariantType.Int64],
        [ua.VariantType.Int64],
    )

    await move.add_method(
        ua.NodeId("move_relativ", idx),
        ua.QualifiedName("move_relativ", idx),
        move_relativ,
        [ua.VariantType.Int64, ua.VariantType.Int64],
        [ua.VariantType.Int64],
    )

    await move.add_method(
        ua.NodeId("move_absolut", idx),
        ua.QualifiedName("move_absolut", idx),
        move_absolut,
        [ua.VariantType.Int64, ua.VariantType.Int64, ua.VariantType.Int64],
        [ua.VariantType.Int64],
    )

    await move.add_method(
        ua.NodeId("push_card_in", idx),
        ua.QualifiedName("push_card_in", idx),
        push_card_in,
        [],
        [],
    )

    await move.add_method(
        ua.NodeId("push_card_out", idx),
        ua.QualifiedName("push_card_out", idx),
        push_card_out,
        [],
        [],
    )

    await order.add_method(
        ua.NodeId("add_new_order", idx),
        ua.QualifiedName("add_new_order", idx),
        add_new_order,
        [
            ua.Argument(" Material", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Variant", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Name", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Title", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Phone", ua.NodeId(ua.ObjectIds.String), -1),
            ua.Argument(" Mail", ua.NodeId(ua.ObjectIds.String), -1),
        ],
        [ua.VariantType.Int64],
    )
    await order.add_method(
        ua.NodeId("get_order_status", idx),
        ua.QualifiedName("get_order_status", idx),
        get_order_status,
        [ua.VariantType.Int64],
        [ua.VariantType.String],
    )
    await order.add_method(
        ua.NodeId("mark_done", idx),
        ua.QualifiedName("mark_done", idx),
        mark_done,
        [ua.VariantType.Int64],
        [ua.VariantType.Boolean],
    )

    # --- ADDED ---
    await gcode.add_method(
        ua.NodeId("put_gcode", idx),
        ua.QualifiedName("put_gcode", idx),
        put_gcode,
        [ua.VariantType.String, ua.VariantType.ByteString],
        [ua.VariantType.Int64],
    )

    await gcode.add_method(
    ua.NodeId("put_file", idx),
    ua.QualifiedName("put_file", idx),
    put_file,
    [ua.VariantType.String, ua.VariantType.ByteString],
    [ua.VariantType.Boolean],
    )

    async with server:
        while True:
            await asyncio.sleep(1)
            await is_connected.write_value(laser.connected())
            await is_mcu_connected.write_value(laser.esp_connected())
            await is_running.write_value(laser.running())
            await progress.write_value(int(laser.get_progress() * 100 ))

            await list_of_files.write_value(laser.list_files())

            await next_order.write_value(str(orders.get_next_order()))
            await todo_list.write_value(str(orders.get_todo_list()))
            await done_list.write_value(str(orders.get_done_list()))
            await count_todo.write_value(orders.get_count_todo())
            await count_done.write_value(orders.get_count_done())

if __name__ == "__main__":
    laser = Laser(dummy=True)
    generate = Generate_Gcode()
    orders = Orders()
    asyncio.run(main(), debug=False)
