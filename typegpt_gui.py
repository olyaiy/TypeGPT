import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import signal

class TypeGPTGUI:
    def __init__(self, master):
        self.master = master
        master.title("TypeGPT Manager")
        master.geometry("400x300")

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(expand=1, fill="both")

        self.keys_frame = ttk.Frame(self.notebook)
        self.status_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.keys_frame, text="API Keys")
        self.notebook.add(self.status_frame, text="Program Status")

        self.setup_keys_frame()
        self.setup_status_frame()

        self.process = None

    def setup_keys_frame(self):
        self.key_entries = {}
        keys = ["OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"]

        for i, key in enumerate(keys):
            label = ttk.Label(self.keys_frame, text=f"{key}:")
            label.grid(row=i, column=0, padx=5, pady=5, sticky="e")

            entry = ttk.Entry(self.keys_frame, width=40)
            entry.grid(row=i, column=1, padx=5, pady=5)
            self.key_entries[key] = entry

        save_button = ttk.Button(self.keys_frame, text="Save Keys", command=self.save_keys)
        save_button.grid(row=len(keys), column=0, columnspan=2, pady=10)

        self.load_keys()

    def setup_status_frame(self):
        self.status_label = ttk.Label(self.status_frame, text="Status: Not Running")
        self.status_label.pack(pady=10)

        self.start_button = ttk.Button(self.status_frame, text="Start TypeGPT", command=self.start_program)
        self.start_button.pack(pady=5)

        self.stop_button = ttk.Button(self.status_frame, text="Stop TypeGPT", command=self.stop_program, state="disabled")
        self.stop_button.pack(pady=5)

    def load_keys(self):
        try:
            with open('keys.txt', 'r') as file:
                for line in file:
                    key, value = line.strip().split('=')
                    if key in self.key_entries:
                        self.key_entries[key].delete(0, tk.END)
                        self.key_entries[key].insert(0, value)
        except FileNotFoundError:
            messagebox.showwarning("Warning", "keys.txt not found. Creating a new file.")

    def save_keys(self):
        with open('keys.txt', 'w') as file:
            for key, entry in self.key_entries.items():
                file.write(f"{key}={entry.get()}\n")
        messagebox.showinfo("Success", "API keys saved successfully!")

    def start_program(self):
        if self.process is None:
            try:
                self.process = subprocess.Popen(['python', 'TypeGPT.py'])
                self.status_label.config(text="Status: Running")
                self.start_button.config(state="disabled")
                self.stop_button.config(state="normal")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start TypeGPT: {str(e)}")

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