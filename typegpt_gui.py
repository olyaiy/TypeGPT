import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import signal
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KEYS_FILE = BASE_DIR / 'keys.txt'
RESTART_EXIT_CODE = 42

class TypeGPTGUI:
    def __init__(self, master):
        self.master = master
        master.title("TypeGPT Manager")
        master.geometry("520x460")
        
        master.configure(padx=20, pady=20)
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.configure('TButton', padding=10)
        style.configure('TEntry', padding=5)
        style.configure('TNotebook', padding=5)

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(expand=1, fill="both", padx=5, pady=5)

        self.keys_frame = ttk.Frame(self.notebook)
        self.status_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.status_frame, text="Program Status")
        self.notebook.add(self.keys_frame, text="API Keys")

        self.setup_status_frame()
        self.setup_keys_frame()

        self.process = None

    def setup_keys_frame(self):
        self.keys_frame.grid_columnconfigure(1, weight=1)
        
        self.key_entries = {}
        keys = ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY"]

        for i, key in enumerate(keys):
            label = ttk.Label(self.keys_frame, text=f"{key}:", font=('Arial', 10))
            label.grid(row=i, column=0, padx=10, pady=10, sticky="e")

            entry = ttk.Entry(self.keys_frame, width=40, show="*")
            entry.grid(row=i, column=1, padx=10, pady=10, sticky="ew")
            self.key_entries[key] = entry

        save_button = ttk.Button(self.keys_frame, text="Save Keys", command=self.save_keys)
        save_button.grid(row=len(keys), column=0, columnspan=2, pady=20)

        self.load_keys()

    def setup_status_frame(self):
        self.status_frame.grid_columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(
            self.status_frame, 
            text="Status: Not Running",
            font=('Arial', 14, 'bold')
        )
        self.status_label.pack(pady=30)

        button_frame = ttk.Frame(self.status_frame)
        button_frame.pack(pady=20)

        style = ttk.Style()
        style.configure('Action.TButton', font=('Arial', 12, 'bold'), padding=(15, 20))

        self.start_button = ttk.Button(
            button_frame, 
            text="Start TypeGPT", 
            command=self.start_program,
            width=25,
            style='Action.TButton'
        )
        self.start_button.pack(pady=15)

        self.stop_button = ttk.Button(
            button_frame, 
            text="Stop TypeGPT", 
            command=self.stop_program,
            width=25,
            style='Action.TButton',
            state="disabled"
        )
        self.stop_button.pack(pady=15)

    def load_keys(self):
        try:
            with open(KEYS_FILE, 'r') as file:
                for line in file:
                    if '=' not in line:
                        continue
                    key, value = line.strip().split('=', 1)
                    if key in self.key_entries:
                        self.key_entries[key].delete(0, tk.END)
                        self.key_entries[key].insert(0, value)
        except FileNotFoundError:
            messagebox.showwarning("Warning", "keys.txt not found. Enter your keys and click Save Keys.")

    def save_keys(self):
        with open(KEYS_FILE, 'w') as file:
            for key, entry in self.key_entries.items():
                file.write(f"{key}={entry.get()}\n")
        messagebox.showinfo("Success", "API keys saved successfully!")

    def start_program(self):
        if self.process is None:
            try:
                self.status_label.config(text="Status: Starting...")
                self.start_button.config(state="disabled")
                self.stop_button.config(state="normal")
                self.master.update()
                
                self._launch()
                
                self.master.after(500, self._check_process_status)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start TypeGPT: {str(e)}")
                self.status_label.config(text="Status: Error")
                self.start_button.config(state="normal")
                self.stop_button.config(state="disabled")

    def _launch(self):
        self.process = subprocess.Popen([sys.executable, str(BASE_DIR / 'TypeGPT.py')], cwd=BASE_DIR)
        self.status_label.config(text="Status: Running")

    def _check_process_status(self):
        if self.process:
            exit_code = self.process.poll()
            if exit_code == RESTART_EXIT_CODE:
                self._launch()
                self.master.after(1000, self._check_process_status)
            elif exit_code is not None:
                self.process = None
                self.status_label.config(text="Status: Not Running")
                self.start_button.config(state="normal")
                self.stop_button.config(state="disabled")
            else:
                self.master.after(1000, self._check_process_status)

    def stop_program(self):
        if self.process:
            os.kill(self.process.pid, signal.SIGTERM)
            self.process = None
            self.status_label.config(text="Status: Not Running")
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = TypeGPTGUI(root)
    root.mainloop()