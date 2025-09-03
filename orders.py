import json
import os
from datetime import datetime

class Orders:
    def __init__(self, dir: str = "~/data",
                 file_in: str = "order.json",
                 file_out: str = "done.json"):
        self.dir = os.path.expanduser(dir)
        self.file_in = os.path.join(self.dir, file_in)
        self.file_out = os.path.join(self.dir, file_out)
        os.makedirs(self.dir, exist_ok=True)

        # Initialisiere die JSON-Dateien, falls sie nicht existieren
        for file in [self.file_in, self.file_out]:
            if not os.path.exists(file):
                with open(file, 'w') as f:
                    json.dump([], f)

    def _read_json(self, file_path):
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_json(self, file_path, data):
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)

    def _get_next_order_number(self):
        todo_orders = self._read_json(self.file_in)
        done_orders = self._read_json(self.file_out)
        all_orders = todo_orders + done_orders
        return max([order["order_number"] for order in all_orders], default=0) + 1

    def add_new_order(self, material, variant, name, title, phone, mail):
        orders = self._read_json(self.file_in)
        order_number = self._get_next_order_number()
        new_order = {
            "order_number": order_number,
            "material": material,
            "variant": variant,
            "name": name,
            "title": title,
            "phone": phone,
            "mail": mail,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        orders.append(new_order)
        self._write_json(self.file_in, orders)
        return order_number

    def get_next_order(self):
        orders = sorted(self._read_json(self.file_in), key=lambda x: x["date"])
        return orders[0] if orders else None

    def mark_done(self, order_number):
        orders = self._read_json(self.file_in)
        done_orders = self._read_json(self.file_out)
        for order in orders:
            if order["order_number"] == order_number:
                order["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                done_orders.append(order)
                orders.remove(order)
                self._write_json(self.file_in, orders)
                self._write_json(self.file_out, done_orders)
                return True
        print(f"Warnung: Bestellung {order_number} nicht gefunden.")
        return False

    def get_order_status(self, order_number):
        todo_orders = self._read_json(self.file_in)
        done_orders = self._read_json(self.file_out)
        for order in todo_orders:
            if order["order_number"] == order_number:
                return "todo"
        for order in done_orders:
            if order["order_number"] == order_number:
                return "done"
        return "not found"

    def get_todo_list(self):
        return self._read_json(self.file_in)

    def get_done_list(self):
        return self._read_json(self.file_out)

    def get_count_todo(self):
        return len(self._read_json(self.file_in))

    def get_count_done(self):
        return len(self._read_json(self.file_out))
