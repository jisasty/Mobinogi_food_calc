import tkinter as tk
from tkinter import messagebox
import json
from collections import defaultdict
from math import ceil
import sys
import os

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller 임시 폴더 경로
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_json(filename):
    path = resource_path(filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

recipes = load_json("음식.json")
gatherables = load_json("채집.json")
processed = load_json("식재료.json")
purchasables = load_json("구매가능.json")

categorized_dishes = {
    "간편": ["여행자 간식", "달걀프라이", "삶은 달걀"],
    "힘 특화": ["구운 고기", "마요네즈 고기 볶음", "포크 인 밀크", "치즈 퐁뒤", "조개찜", "크림소스 스테이크", "사와르마", "미트 파르미자나"],
    "솜씨 특화": ["통감자구이", "감자 샐러드", "야채볶음", "리코타 치즈 샐러드", "감자수프", "알리오 올리오", "두부 스테이크", "두부 국수"],
    "지력 특화": ["사과 주스", "사과 샐러드", "콘치즈", "사과 수플레", "얼음 딸기주스", "사과 생크림케이크", "두유 빙수", "두유 파스닙 케이크"],
    "쉐어링": ["흰살생선 뫼니에르", "부야베스", "고등어와 연어 스테이크", "메기 피시 앤 칩스", "농어 매운탕"]
}

user_inventory = {}

# 재귀적으로 필요한 재료들을 모두 계산하면서, 각 재료별로 필요한 하위 재료도 함께 기록
def resolve_ingredients(item_name, quantity_needed):
    """
    결과 구조 예시:
    {
        'item_name': {
            'quantity': n,
            'source': '채집'/'가공'/'구매'/...
            'price': x,
            'time_seconds': y,
            'needs': { 'sub_item': sub_qty, ... }  # 가공 재료가 필요할 때만
        }
    }
    """
    results = {}

    owned = user_inventory.get(item_name, 0)
    quantity_needed = max(0, quantity_needed - owned)
    if quantity_needed == 0:
        return results  # 필요 없음

    if item_name in processed:
        recipe = processed[item_name]
        output_qty = recipe["quantity"]
        craft_times = ceil(quantity_needed / output_qty)

        needs = defaultdict(int)

        for sub_item, sub_qty in recipe["ingredients"].items():
            sub_results = resolve_ingredients(sub_item, sub_qty * craft_times)
            for k, v in sub_results.items():
                if k in results:
                    results[k]['quantity'] += v['quantity']
                    results[k]['price'] += v['price']
                    results[k]['time_seconds'] += v['time_seconds']
                    # 하위 재료의 needs까지 모두 누적
                    for nk, nv in v.get('needs', {}).items():
                        needs[nk] += nv
                else:
                    results[k] = v.copy()
                    for nk, nv in v.get('needs', {}).items():
                        needs[nk] += nv

            needs[sub_item] += sub_qty * craft_times

        results[item_name] = {
            "quantity": quantity_needed,
            "source": "가공",
            "price": 0,
            "time_seconds": recipe.get("time_seconds", 0) * craft_times,
            "needs": dict(needs)
        }

    elif item_name in gatherables:
        required = gatherables[item_name].get("requires", {})
        if isinstance(required, list):
            required = {}

        output = gatherables[item_name].get("produces", 1)
        gather_times = ceil(quantity_needed / output)

        needs = defaultdict(int)
        for sub_item, sub_qty in required.items():
            sub_results = resolve_ingredients(sub_item, sub_qty * gather_times)
            for k, v in sub_results.items():
                if k in results:
                    results[k]['quantity'] += v['quantity']
                    results[k]['price'] += v['price']
                    results[k]['time_seconds'] += v['time_seconds']
                    for nk, nv in v.get('needs', {}).items():
                        needs[nk] += nv
                else:
                    results[k] = v.copy()
                    for nk, nv in v.get('needs', {}).items():
                        needs[nk] += nv
            needs[sub_item] += sub_qty * gather_times

        results[item_name] = {
            "quantity": quantity_needed,
            "source": "채집",
            "price": 0,
            "time_seconds": 0,
            "needs": dict(needs)
        }

    elif item_name in purchasables:
        results[item_name] = {
            "quantity": quantity_needed,
            "source": "구매",
            "price": purchasables[item_name] * quantity_needed,
            "time_seconds": 0,
            "needs": {}
        }
    else:
        results[item_name] = {
            "quantity": quantity_needed,
            "source": "미지정",
            "price": 0,
            "time_seconds": 0,
            "needs": {}
        }

    return results

def merge_results(main, new):
    # results를 합쳐주는 함수 (quantity, price, time_seconds 합산)
    for k, v in new.items():
        if k in main:
            main[k]['quantity'] += v['quantity']
            main[k]['price'] += v['price']
            main[k]['time_seconds'] += v['time_seconds']
            # needs는 후순위
            for nk, nv in v.get('needs', {}).items():
                if 'needs' not in main[k]:
                    main[k]['needs'] = {}
                main[k]['needs'][nk] = main[k]['needs'].get(nk, 0) + nv
        else:
            main[k] = v.copy()

def compute_full_recipe(dish_name, count):
    if dish_name not in recipes:
        return None

    total = {}

    for ingredient, qty in recipes[dish_name]["ingredients"].items():
        result = resolve_ingredients(ingredient, qty * count)
        merge_results(total, result)

    total_cost = sum(v["price"] for v in total.values())
    total_time = sum(v["time_seconds"] for v in total.values())

    return {
        "details": total,
        "total_cost": total_cost,
        "total_time": total_time
    }

class App:
    def __init__(self, master):
        self.master = master
        master.title("모비노기 요리 재료 계산기")

        master.geometry("1100x550")
        master.resizable(False, False)

        self.category_frame = tk.Frame(master)
        self.category_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        self.item_frame = tk.Frame(master)
        self.item_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        self.right_frame = tk.Frame(master)
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.inventory_label = tk.Label(self.right_frame, text="보유한 재료", font=("Arial", 12, "bold"))
        self.inventory_label.grid(row=0, column=0, sticky="w")

        self.inventory_frame = tk.Frame(self.right_frame)
        self.inventory_frame.grid(row=1, column=0, sticky="n")

        self.need_label = tk.Label(self.right_frame, text="필요한 재료", font=("Arial", 12, "bold"))
        self.need_label.grid(row=0, column=1, sticky="w", padx=(20,0))

        self.result_text = tk.Text(self.right_frame, height=35, width=70, state="disabled")
        self.result_text.grid(row=1, column=1, sticky="n")

        self.count_frame = tk.Frame(self.right_frame)
        self.count_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky="w")

        tk.Label(self.count_frame, text="만들 개수:").pack(side=tk.LEFT)
        self.count_entry = tk.Entry(self.count_frame, width=10)
        self.count_entry.pack(side=tk.LEFT, padx=5)
        self.count_entry.insert(0, "1")

        self.calc_button = tk.Button(self.count_frame, text="계산하기", command=self.calculate)
        self.calc_button.pack(side=tk.LEFT, padx=10)

        self.selected_category = None
        self.selected_dish = None
        self.inventory_entries = {}

        self.category_buttons = {}
        for category in categorized_dishes:
            btn = tk.Button(self.category_frame, text=category, width=15, command=lambda c=category: self.toggle_category(c))
            btn.pack(pady=3)
            self.category_buttons[category] = btn

        self.item_buttons = {}

    def toggle_category(self, category):
        if self.selected_category == category:
            self.clear_item_buttons()
            self.selected_category = None
        else:
            self.selected_category = category
            self.show_items(category)

    def clear_item_buttons(self):
        for btn in self.item_buttons.values():
            btn.destroy()
        self.item_buttons.clear()
        self.selected_dish = None
        self.clear_inventory_inputs()
        self.clear_result_text()

    def show_items(self, category):
        self.clear_item_buttons()
        for dish_name in categorized_dishes[category]:
            if dish_name not in recipes:
                continue
            btn = tk.Button(self.item_frame, text=dish_name, width=25, command=lambda d=dish_name: self.select_dish(d))
            btn.pack(pady=2)
            self.item_buttons[dish_name] = btn
        self.clear_inventory_inputs()
        self.clear_result_text()

    def clear_inventory_inputs(self):
        for widget in self.inventory_frame.winfo_children():
            widget.destroy()
        self.inventory_entries.clear()

    def clear_result_text(self):
        self.result_text.config(state="normal")
        self.result_text.delete(1.0, tk.END)
        self.result_text.config(state="disabled")

    def select_dish(self, dish_name):
        self.selected_dish = dish_name

        for widget in self.inventory_frame.winfo_children():
            widget.destroy()
        self.inventory_entries.clear()

        for ingredient in recipes[dish_name]["ingredients"]:
            row = tk.Frame(self.inventory_frame)
            row.pack(anchor="w", pady=2, fill="x")

            label = tk.Label(row, text=f"{ingredient}:", width=15, anchor="w")
            label.pack(side=tk.LEFT)

            entry = tk.Entry(row, width=15)
            entry.pack(side=tk.LEFT, padx=5)
            entry.insert(0, "0")
            self.inventory_entries[ingredient] = entry

        self.clear_result_text()

    def calculate(self):
        global user_inventory
        user_inventory = {}

        if not self.selected_dish:
            messagebox.showwarning("경고", "요리를 먼저 선택하세요.")
            return
        try:
            count = int(self.count_entry.get())
            if count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("오류", "유효한 개수를 입력하세요.")
            return

        for item, entry in self.inventory_entries.items():
            try:
                owned = int(entry.get())
                if owned > 0:
                    user_inventory[item] = owned
            except:
                continue

        result = compute_full_recipe(self.selected_dish, count)
        if result is None:
            messagebox.showerror("오류", "레시피를 찾을 수 없습니다.")
            return

        grouped = {
            "채집": {},
            "가공": {},
            "구매": {},
            "미지정": {}
        }

        for item, info in result["details"].items():
            source = info["source"] or "미지정"
            if source == "가공" and item not in processed:
                source = "미지정"
            if source not in grouped:
                source = "미지정"
            grouped[source][item] = info

        self.result_text.config(state="normal")
        self.result_text.delete(1.0, tk.END)

        self.result_text.insert(tk.END, f"요리: {self.selected_dish} x {count}\n\n")
        self.result_text.insert(tk.END, f"총 비용: {result['total_cost']} G\n")
        self.result_text.insert(tk.END, f"총 가공 시간: {result['total_time']} 초\n\n")

        self.result_text.insert(tk.END, "재료 상세:\n\n")

        def print_group(title, group, explain=None):
            if not group:
                return
            self.result_text.insert(tk.END, f"■ {title}\n")
            for item, info in sorted(group.items()):
                price_text = ""
                if title == "구매 재료":
                    price_text = f", 가격: {info['price']} G"
                self.result_text.insert(tk.END, f"□ {item}: {info['quantity']}개{price_text}\n")
                needs = info.get("needs", {})
                if needs:
                    needs_text = ", ".join(f"{k} {v}개" for k, v in sorted(needs.items()))
                    self.result_text.insert(tk.END, f"▶ 필요 재료: {needs_text}\n")
            if explain:
                self.result_text.insert(tk.END, explain + "\n")
            self.result_text.insert(tk.END, "\n")

        print_group("채집 재료", grouped["채집"])
        print_group("식자재 가공 재료", grouped["가공"])
        print_group("구매 재료", grouped["구매"])
        print_group("미지정 재료", grouped["미지정"])

        self.result_text.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    root.iconbitmap(resource_path("icon.ico"))  # 아이콘 경로 맞게 수정하세요
    app = App(root)
    root.mainloop()
