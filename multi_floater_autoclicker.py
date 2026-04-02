# multi_floater_autoclicker.py
"""
Auto-Clicker（Python + tkinter + pyautogui）
热键：↑开始，↓停止，←添加按钮，→退出（窗口聚焦时）
布局管理：支持多布局保存/加载/删除，文件位于 layouts/*.json
录制功能：支持全局鼠标点击录制与回放，文件位于 records/*.json
"""

import ctypes
import json
import os
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import pyautogui

try:
    from pynput import keyboard as pynput_keyboard
    from pynput import mouse as pynput_mouse
except Exception:
    pynput_keyboard = None
    pynput_mouse = None

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
LAYOUT_DIR = os.path.join(SCRIPT_DIR, "layouts")
RECORD_DIR = os.path.join(SCRIPT_DIR, "records")
os.makedirs(LAYOUT_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)

try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass


def normalize_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    name = name.replace(" ", "_")
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("._")
    return name


def layout_path(name: str) -> str:
    safe = normalize_name(name)
    return os.path.join(LAYOUT_DIR, f"{safe}.json")


def list_layout_names():
    names = []
    if os.path.exists(LAYOUT_DIR):
        for fn in os.listdir(LAYOUT_DIR):
            if fn.lower().endswith(".json"):
                names.append(os.path.splitext(fn)[0])
    names.sort(key=str.lower)
    return names


def record_path(name: str) -> str:
    safe = normalize_name(name)
    return os.path.join(RECORD_DIR, f"{safe}.json")


def list_record_names():
    names = []
    if os.path.exists(RECORD_DIR):
        for fn in os.listdir(RECORD_DIR):
            if fn.lower().endswith(".json"):
                names.append(os.path.splitext(fn)[0])
    names.sort(key=str.lower)
    return names


class FloatingButton:
    def __init__(self, master, label="Btn", x=100, y=100, alpha=0.45):
        self.master = master
        self.label = label
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", alpha)

        self.frame = tk.Frame(self.win, bd=1, relief="raised")
        self.frame.pack()
        self.btn = tk.Button(self.frame, text=self.label, width=8)
        self.btn.pack()
        self.win.geometry(f"+{x}+{y}")

        self._drag_start_x = 0
        self._drag_start_y = 0
        self.frame.bind("<ButtonPress-1>", self._on_press)
        self.frame.bind("<B1-Motion>", self._on_motion)
        self.btn.bind("<ButtonPress-1>", self._on_press)
        self.btn.bind("<B1-Motion>", self._on_motion)

    def _on_press(self, event):
        self._drag_start_x = event.x_root - self.win.winfo_x()
        self._drag_start_y = event.y_root - self.win.winfo_y()

    def _on_motion(self, event):
        new_x = event.x_root - self._drag_start_x
        new_y = event.y_root - self._drag_start_y
        self.win.geometry(f"+{new_x}+{new_y}")

    def get_center(self):
        self.win.update_idletasks()
        x = self.win.winfo_x()
        y = self.win.winfo_y()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        return x + w // 2, y + h // 2

    def move_to(self, x, y):
        self.win.geometry(f"+{x}+{y}")

    def hide(self):
        self.win.withdraw()

    def show(self):
        self.win.deiconify()

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass


class App:
    def __init__(self, root):
        self.root = root
        root.title("Auto-Clicker - 管理面板")
        root.geometry("1280x860")
        root.minsize(1100, 760)
        try:
            root.state("zoomed")
        except Exception:
            pass
        root.resizable(True, True)

        self.current_layout_name = "default"
        self.current_record_name = "record_default"

        tk.Label(root, text="悬浮按钮列表（选择项）").pack(anchor="w", padx=8, pady=(6, 0))
        self.listbox = tk.Listbox(root, height=8, width=120)
        self.listbox.pack(padx=8, pady=(0, 6))

        frm = tk.Frame(root)
        frm.pack(padx=8, pady=4, fill="x")
        tk.Button(frm, text="添加按钮", command=self.add_button).grid(row=0, column=0, padx=4, pady=2)
        tk.Button(frm, text="删除按钮", command=self.remove_button).grid(row=0, column=1, padx=4)
        tk.Button(frm, text="上移", command=self.move_up).grid(row=0, column=2, padx=4)
        tk.Button(frm, text="下移", command=self.move_down).grid(row=0, column=3, padx=4)
        tk.Button(frm, text="设为当前鼠标位置", command=self.set_pos).grid(row=0, column=4, padx=4)

        paramfrm = tk.Frame(root)
        paramfrm.pack(padx=8, pady=4, fill="x")
        tk.Label(paramfrm, text="间隔 (ms):").grid(row=0, column=0, sticky="e")
        self.interval_var = tk.StringVar(value="100")
        tk.Entry(paramfrm, textvariable=self.interval_var, width=8).grid(row=0, column=1, sticky="w", padx=(4, 12))
        tk.Label(paramfrm, text="重复次数 (0=无限):").grid(row=0, column=2, sticky="e")
        self.repeat_var = tk.StringVar(value="1")
        tk.Entry(paramfrm, textvariable=self.repeat_var, width=8).grid(row=0, column=3, sticky="w", padx=4)

        layoutfrm = tk.Frame(root)
        layoutfrm.pack(padx=8, pady=4, fill="x")
        tk.Label(layoutfrm, text="当前布局:").grid(row=0, column=0, sticky="e")
        self.layout_label_var = tk.StringVar(value=self.current_layout_name)
        tk.Label(layoutfrm, textvariable=self.layout_label_var, fg="#1a73e8").grid(row=0, column=1, sticky="w", padx=(4, 12))

        tk.Button(layoutfrm, text="保存布局", width=10, command=self.save_cfg).grid(row=0, column=2, padx=4)
        tk.Button(layoutfrm, text="加载布局", width=10, command=self.load_cfg).grid(row=0, column=3, padx=4)
        tk.Button(layoutfrm, text="布局列表", width=10, command=self.show_layouts).grid(row=0, column=4, padx=4)

        tk.Label(layoutfrm, text="快速切换:").grid(row=0, column=5, padx=(12, 4), sticky="e")
        self.layout_selector_var = tk.StringVar(value="")
        self.layout_selector = ttk.Combobox(layoutfrm, textvariable=self.layout_selector_var, state="readonly", width=18, values=[])
        self.layout_selector.grid(row=0, column=6, padx=4)
        self.layout_selector.bind("<<ComboboxSelected>>", self.on_layout_selected)

        tk.Button(layoutfrm, text="刷新", width=8, command=self.refresh_layout_selector).grid(row=0, column=7, padx=4)
        tk.Button(layoutfrm, text="删除布局", width=10, command=self.delete_selected_layout).grid(row=0, column=8, padx=4)

        recordfrm = tk.Frame(root)
        recordfrm.pack(padx=8, pady=4, fill="x")
        tk.Label(recordfrm, text="当前录制:").grid(row=0, column=0, sticky="e")
        self.record_label_var = tk.StringVar(value=self.current_record_name)
        tk.Label(recordfrm, textvariable=self.record_label_var, fg="#0b8043").grid(row=0, column=1, sticky="w", padx=(4, 12))

        self.rec_start_btn = tk.Button(recordfrm, text="开始录制", width=10, command=self.start_recording)
        self.rec_start_btn.grid(row=0, column=2, padx=4)
        self.rec_stop_btn = tk.Button(recordfrm, text="停止录制", width=10, command=self.stop_recording)
        self.rec_stop_btn.grid(row=0, column=3, padx=4)
        tk.Button(recordfrm, text="回放录制", width=10, command=self.play_recording).grid(row=0, column=4, padx=4)
        tk.Button(recordfrm, text="保存录制", width=10, command=self.save_recording).grid(row=0, column=5, padx=4)
        tk.Button(recordfrm, text="加载录制", width=10, command=self.load_recording).grid(row=0, column=6, padx=4)

        tk.Label(recordfrm, text="录制切换:").grid(row=0, column=7, padx=(12, 4), sticky="e")
        self.record_selector_var = tk.StringVar(value="")
        self.record_selector = ttk.Combobox(recordfrm, textvariable=self.record_selector_var, state="readonly", width=16, values=[])
        self.record_selector.grid(row=0, column=8, padx=4)
        self.record_selector.bind("<<ComboboxSelected>>", self.on_record_selected)
        tk.Button(recordfrm, text="删除录制", width=10, command=self.delete_selected_record).grid(row=0, column=9, padx=4)

        statusfrm = tk.Frame(root)
        statusfrm.pack(padx=8, pady=(2, 8), fill="x")
        tk.Label(statusfrm, text="状态:").pack(side="left")
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(statusfrm, textvariable=self.status_var, fg="#5f6368").pack(side="left", padx=(6, 0))

        runfrm = tk.Frame(root)
        runfrm.pack(padx=8, pady=8, fill="x")
        self.start_btn = tk.Button(runfrm, text="开始 (↑)", width=12, command=self.start_play)
        self.start_btn.grid(row=0, column=0, padx=4)
        tk.Button(runfrm, text="停止 (↓)", width=10, command=self.stop_play).grid(row=0, column=1, padx=4)
        tk.Button(runfrm, text="退出 (→)", width=10, command=self.exit_app).grid(row=0, column=2, padx=4)

        self.buttons = []
        self.play_thread = None
        self.stop_event = threading.Event()
        self.playing = False

        self.recording = False
        self.record_events = []
        self.record_start_ts = 0.0
        self.record_listener = None
        self.record_play_thread = None
        self.record_play_stop_event = threading.Event()
        self.record_playing = False

        self._last_add_key_ts = 0.0
        self._last_hotkey_ts = {}
        self.hotkey_listener = None

        root.bind_all("<Up>", lambda e: self.start_play())
        root.bind_all("<Down>", lambda e: self.stop_all())
        root.bind_all("<Left>", lambda e: self.add_button_hotkey())
        root.bind_all("<Right>", lambda e: self.exit_app())

        # 默认尽量占满屏幕，避免控件过多看不全
        self._start_global_hotkeys()
        self.refresh_layout_selector()
        self.refresh_record_selector()

        names = list_layout_names()
        if "default" in names:
            self.load_cfg("default", silent=True)
        elif names:
            self.load_cfg(names[0], silent=True)

    # ---------- Global hotkeys ----------
    def _start_global_hotkeys(self):
        if pynput_keyboard is None:
            print("global hotkey disabled: pynput not installed, fallback to window-focused hotkeys")
            return
        try:
            self.hotkey_listener = pynput_keyboard.Listener(on_press=self._on_global_key_press)
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
            print("global hotkeys enabled")
        except Exception as e:
            print("global hotkey disabled:", e)

    def _stop_global_hotkeys(self):
        try:
            if self.hotkey_listener:
                self.hotkey_listener.stop()
                self.hotkey_listener = None
        except Exception:
            pass

    def _hotkey_debounce(self, name, min_gap=0.15):
        now = time.time()
        prev = self._last_hotkey_ts.get(name, 0.0)
        if now - prev < min_gap:
            return False
        self._last_hotkey_ts[name] = now
        return True

    def _on_global_key_press(self, key):
        if pynput_keyboard is None:
            return
        try:
            if key == pynput_keyboard.Key.up and self._hotkey_debounce("up"):
                self.root.after(0, self.start_play)
            elif key == pynput_keyboard.Key.down and self._hotkey_debounce("down"):
                self.root.after(0, self.stop_all)
            elif key == pynput_keyboard.Key.left and self._hotkey_debounce("left"):
                self.root.after(0, self.add_button_hotkey)
            elif key == pynput_keyboard.Key.right and self._hotkey_debounce("right"):
                self.root.after(0, self.exit_app)
        except Exception:
            pass

    # ---------- Float buttons ----------
    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for i, fb in enumerate(self.buttons, start=1):
            try:
                x = fb.win.winfo_x()
                y = fb.win.winfo_y()
            except Exception:
                x = y = 0
            self.listbox.insert(tk.END, f"{i}: {fb.label}  ({x},{y})")

    def add_button_hotkey(self):
        now = time.time()
        if now - self._last_add_key_ts < 0.2:
            return
        self._last_add_key_ts = now
        self.add_button()

    def add_button(self):
        mx, my = pyautogui.position()
        idx = len(self.buttons) + 1
        label = f"Btn{idx}"
        fb = FloatingButton(self.root, label=label, x=mx, y=my, alpha=0.45)
        self.buttons.append(fb)
        self.refresh_listbox()

    def remove_button(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选择要删除的按钮。")
            return
        idx = sel[0]
        fb = self.buttons.pop(idx)
        fb.destroy()
        self.refresh_listbox()

    def move_up(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == 0:
            return
        self.buttons[idx - 1], self.buttons[idx] = self.buttons[idx], self.buttons[idx - 1]
        self.refresh_listbox()
        self.listbox.select_set(idx - 1)

    def move_down(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.buttons) - 1:
            return
        self.buttons[idx + 1], self.buttons[idx] = self.buttons[idx], self.buttons[idx + 1]
        self.refresh_listbox()
        self.listbox.select_set(idx + 1)

    def set_pos(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个按钮以设置其位置。")
            return
        idx = sel[0]
        mx, my = pyautogui.position()
        self.buttons[idx].move_to(mx, my)
        self.refresh_listbox()

    # ---------- Layouts ----------
    def _collect_layout_data(self):
        data = []
        for fb in self.buttons:
            try:
                x = fb.win.winfo_x()
                y = fb.win.winfo_y()
            except Exception:
                x = y = 0
            data.append({"label": fb.label, "x": x, "y": y})
        return data

    def refresh_layout_selector(self):
        names = list_layout_names()
        self.layout_selector["values"] = names
        if self.current_layout_name in names:
            self.layout_selector_var.set(self.current_layout_name)
        elif names:
            self.layout_selector_var.set(names[0])
        else:
            self.layout_selector_var.set("")

    def on_layout_selected(self, _event=None):
        name = self.layout_selector_var.get().strip()
        if name:
            self.load_cfg(name=name, silent=False)

    def save_cfg(self):
        name = simpledialog.askstring("保存布局", "请输入布局名称：", initialvalue=self.current_layout_name, parent=self.root)
        if name is None:
            return
        name = normalize_name(name)
        if not name:
            messagebox.showerror("错误", "布局名称不能为空。")
            return

        path = layout_path(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._collect_layout_data(), f, ensure_ascii=False, indent=2)

        self.current_layout_name = name
        self.layout_label_var.set(name)
        self.refresh_layout_selector()
        self.status_var.set(f"布局已保存：{name}")

    def show_layouts(self):
        names = list_layout_names()
        if not names:
            messagebox.showinfo("布局列表", "当前没有已保存布局。")
            return
        messagebox.showinfo("布局列表", "可用布局：\n" + "\n".join(names))

    def delete_selected_layout(self):
        name = normalize_name(self.layout_selector_var.get())
        if not name:
            messagebox.showinfo("提示", "请先从下拉框选择要删除的布局。")
            return
        path = layout_path(name)
        if not os.path.exists(path):
            messagebox.showerror("错误", f"未找到布局：{name}")
            self.refresh_layout_selector()
            return
        if not messagebox.askyesno("确认删除", f"确定删除布局 '{name}' 吗？"):
            return

        os.remove(path)
        names = list_layout_names()
        if names:
            next_name = names[0]
            self.load_cfg(next_name, silent=True)
        else:
            self.current_layout_name = "default"
            self.layout_label_var.set(self.current_layout_name)

        self.refresh_layout_selector()
        self.status_var.set(f"已删除布局：{name}")

    def load_cfg(self, name=None, silent=False):
        if not name:
            names = list_layout_names()
            if not names:
                if not silent:
                    messagebox.showinfo("提示", "当前没有已保存布局。")
                return
            prompt = "可用布局：\n" + "\n".join(names) + "\n\n请输入要加载的布局名称："
            name = simpledialog.askstring("加载布局", prompt, initialvalue=self.current_layout_name, parent=self.root)
            if name is None:
                return

        name = normalize_name(name)
        if not name:
            if not silent:
                messagebox.showerror("错误", "布局名称不能为空。")
            return

        path = layout_path(name)
        if not os.path.exists(path):
            if not silent:
                messagebox.showerror("错误", f"未找到布局：{name}")
            return

        for fb in self.buttons:
            fb.destroy()
        self.buttons = []

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for i, it in enumerate(data, start=1):
            label = it.get("label", f"Btn{i}")
            x = int(it.get("x", 100))
            y = int(it.get("y", 100))
            self.buttons.append(FloatingButton(self.root, label=label, x=x, y=y, alpha=0.45))

        self.current_layout_name = name
        self.layout_label_var.set(name)
        self.refresh_layout_selector()
        self.refresh_listbox()
        if not silent:
            self.status_var.set(f"已加载布局：{name}")

    # ---------- Recording ----------
    def refresh_record_selector(self):
        names = list_record_names()
        self.record_selector["values"] = names
        if self.current_record_name in names:
            self.record_selector_var.set(self.current_record_name)
        elif names:
            self.record_selector_var.set(names[0])
        else:
            self.record_selector_var.set("")

    def on_record_selected(self, _event=None):
        name = self.record_selector_var.get().strip()
        if name:
            self.load_recording(name=name)

    def _on_record_click(self, x, y, button, pressed):
        if not self.recording or not pressed:
            return
        if pynput_mouse is None:
            return

        btn = None
        if button == pynput_mouse.Button.left:
            btn = "left"
        elif button == pynput_mouse.Button.right:
            btn = "right"
        elif button == pynput_mouse.Button.middle:
            btn = "middle"

        if btn is None:
            return

        t_ms = int((time.time() - self.record_start_ts) * 1000)
        self.record_events.append({"t": t_ms, "x": int(x), "y": int(y), "button": btn})

    def start_recording(self):
        if self.recording:
            return
        if pynput_mouse is None:
            messagebox.showerror("错误", "录制功能需要 pynput（pip install pynput）。")
            return

        self.stop_record_playback()
        self.record_events = []
        self.record_start_ts = time.time()
        self.recording = True

        try:
            self.record_listener = pynput_mouse.Listener(on_click=self._on_record_click)
            self.record_listener.daemon = True
            self.record_listener.start()
            self.status_var.set("录制中...（点击任意位置，点“停止录制”结束）")
            self.rec_start_btn.config(state="disabled")
            self.rec_stop_btn.config(state="normal")
        except Exception as e:
            self.recording = False
            messagebox.showerror("错误", f"启动录制失败：{e}")

    def stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        try:
            if self.record_listener:
                self.record_listener.stop()
        except Exception:
            pass
        self.record_listener = None

        self.rec_start_btn.config(state="normal")
        self.rec_stop_btn.config(state="normal")
        self.status_var.set(f"录制结束：共 {len(self.record_events)} 个点击事件")

    def save_recording(self):
        if not self.record_events:
            messagebox.showinfo("提示", "当前没有录制事件可保存。")
            return

        name = simpledialog.askstring("保存录制", "请输入录制名称：", initialvalue=self.current_record_name, parent=self.root)
        if name is None:
            return
        name = normalize_name(name)
        if not name:
            messagebox.showerror("错误", "录制名称不能为空。")
            return

        path = record_path(name)
        payload = {
            "name": name,
            "created_at": int(time.time()),
            "events": self.record_events,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        self.current_record_name = name
        self.record_label_var.set(name)
        self.refresh_record_selector()
        self.status_var.set(f"录制已保存：{name}（{len(self.record_events)} 事件）")

    def load_recording(self, name=None):
        if not name:
            names = list_record_names()
            if not names:
                messagebox.showinfo("提示", "当前没有已保存录制。")
                return
            prompt = "可用录制：\n" + "\n".join(names) + "\n\n请输入要加载的录制名称："
            name = simpledialog.askstring("加载录制", prompt, initialvalue=self.current_record_name, parent=self.root)
            if name is None:
                return

        name = normalize_name(name)
        if not name:
            messagebox.showerror("错误", "录制名称不能为空。")
            return

        path = record_path(name)
        if not os.path.exists(path):
            messagebox.showerror("错误", f"未找到录制：{name}")
            return

        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        events = payload.get("events", [])
        if not isinstance(events, list):
            messagebox.showerror("错误", "录制文件格式不正确。")
            return

        self.record_events = events
        self.current_record_name = name
        self.record_label_var.set(name)
        self.refresh_record_selector()
        self.status_var.set(f"录制已加载：{name}（{len(self.record_events)} 事件）")

    def delete_selected_record(self):
        name = normalize_name(self.record_selector_var.get())
        if not name:
            messagebox.showinfo("提示", "请先从下拉框选择要删除的录制。")
            return
        path = record_path(name)
        if not os.path.exists(path):
            messagebox.showerror("错误", f"未找到录制：{name}")
            self.refresh_record_selector()
            return

        if not messagebox.askyesno("确认删除", f"确定删除录制 '{name}' 吗？"):
            return

        os.remove(path)
        self.refresh_record_selector()

        if self.current_record_name == name:
            self.current_record_name = "record_default"
            self.record_label_var.set(self.current_record_name)
            self.record_events = []

        self.status_var.set(f"已删除录制：{name}")

    def play_recording(self):
        if self.recording:
            messagebox.showinfo("提示", "请先停止录制，再回放。")
            return
        if not self.record_events:
            messagebox.showinfo("提示", "当前没有录制事件。")
            return
        if self.record_playing:
            return

        self.record_playing = True
        self.record_play_stop_event.clear()
        self.status_var.set(f"录制回放中：{len(self.record_events)} 事件")
        self.record_play_thread = threading.Thread(target=self._record_playback_loop, daemon=True)
        self.record_play_thread.start()

    def _record_playback_loop(self):
        events = list(self.record_events)
        last_t = 0
        for ev in events:
            if self.record_play_stop_event.is_set():
                break
            t_ms = int(ev.get("t", 0))
            x = int(ev.get("x", 0))
            y = int(ev.get("y", 0))
            btn = ev.get("button", "left")

            wait_ms = max(0, t_ms - last_t)
            slept = 0.0
            total = wait_ms / 1000.0
            while slept < total and not self.record_play_stop_event.is_set():
                d = min(0.02, total - slept)
                time.sleep(d)
                slept += d

            if self.record_play_stop_event.is_set():
                break

            try:
                pyautogui.click(x=x, y=y, button=btn)
            except Exception as e:
                print("record playback click error:", e)

            last_t = t_ms

        self.root.after(0, self._on_record_playback_stopped)

    def _on_record_playback_stopped(self):
        self.record_playing = False
        self.record_play_stop_event.clear()
        self.status_var.set("录制回放结束")

    def stop_record_playback(self):
        if not self.record_playing:
            return
        self.record_play_stop_event.set()
        if self.record_play_thread:
            self.record_play_thread.join(timeout=2)
        self._on_record_playback_stopped()

    # ---------- Auto click ----------
    def start_play(self):
        if self.playing:
            return

        try:
            interval_ms = int(self.interval_var.get())
            repeat = int(self.repeat_var.get())
        except Exception:
            messagebox.showerror("错误", "请确保间隔和重复次数为整数。")
            return

        if len(self.buttons) == 0:
            messagebox.showinfo("提示", "没有悬浮按钮。请先添加按钮。")
            return

        self.playing = True
        self.start_btn.config(text="运行中")
        self._set_float_windows_visible(False)
        self.stop_event.clear()
        self.play_thread = threading.Thread(target=self._playback_loop, args=(interval_ms, repeat), daemon=True)
        self.play_thread.start()

    def stop_play(self):
        if not self.playing:
            return
        self.stop_event.set()
        if self.play_thread:
            self.play_thread.join(timeout=2)
        self._on_play_stopped()

    def stop_all(self):
        self.stop_play()
        self.stop_record_playback()
        self.stop_recording()

    def _playback_loop(self, interval_ms, repeat):
        loop = 0
        while not self.stop_event.is_set():
            loop += 1
            if repeat > 0 and loop > repeat:
                break
            for fb in list(self.buttons):
                if self.stop_event.is_set():
                    break
                try:
                    cx, cy = fb.get_center()
                    pyautogui.click(cx, cy)
                except Exception as e:
                    print("click error:", e)

                waited = 0.0
                total = max(0, interval_ms) / 1000.0
                while waited < total and not self.stop_event.is_set():
                    d = min(0.02, total - waited)
                    time.sleep(d)
                    waited += d

        self.root.after(0, self._on_play_stopped)

    def _on_play_stopped(self):
        self.playing = False
        self.start_btn.config(text="开始 (↑)")
        self._set_float_windows_visible(True)
        self.stop_event.clear()

    def _set_float_windows_visible(self, visible):
        for fb in self.buttons:
            try:
                if visible:
                    fb.show()
                else:
                    fb.hide()
            except Exception:
                pass

    def exit_app(self):
        self._stop_global_hotkeys()
        self.stop_all()
        for fb in self.buttons:
            fb.destroy()
        self.root.destroy()


if __name__ == "__main__":
    print("pyautogui.FAILSAFE =", pyautogui.FAILSAFE)
    root = tk.Tk()
    app = App(root)
    root.mainloop()
