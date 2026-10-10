"""Small Tkinter manager: edit API keys and start/stop TypeGPT."""
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import config

KEYS = ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY']
KEY_FILE = config.ROOT / 'keys.txt'
SCRIPT = config.ROOT / 'TypeGPT.py'


class TypeGPTGUI:
    def __init__(self, master):
        self.master = master
        self.process = None
        master.title('TypeGPT Manager')
        master.geometry('520x360')
        master.configure(padx=20, pady=20)
        master.protocol('WM_DELETE_WINDOW', self.on_close)

        notebook = ttk.Notebook(master)
        notebook.pack(expand=1, fill='both')
        self.status_frame = ttk.Frame(notebook)
        self.keys_frame = ttk.Frame(notebook)
        notebook.add(self.status_frame, text='Program Status')
        notebook.add(self.keys_frame, text='API Keys')
        self.setup_status_frame()
        self.setup_keys_frame()

    def setup_status_frame(self):
        self.status_label = ttk.Label(self.status_frame, text='Status: Not running', font=('Arial', 14, 'bold'))
        self.status_label.pack(pady=30)
        self.start_button = ttk.Button(self.status_frame, text='Start TypeGPT', width=25, command=self.start_program)
        self.start_button.pack(pady=10)
        self.stop_button = ttk.Button(self.status_frame, text='Stop TypeGPT', width=25,
                                      command=self.stop_program, state='disabled')
        self.stop_button.pack(pady=10)

    def setup_keys_frame(self):
        self.keys_frame.grid_columnconfigure(1, weight=1)
        self.key_entries = {}
        existing = config._read_key_file(KEY_FILE)
        for row, key in enumerate(KEYS):
            ttk.Label(self.keys_frame, text=f'{key}:').grid(row=row, column=0, padx=10, pady=10, sticky='e')
            entry = ttk.Entry(self.keys_frame, width=40, show='•')
            entry.grid(row=row, column=1, padx=10, pady=10, sticky='ew')
            entry.insert(0, existing.get(key, ''))
            self.key_entries[key] = entry
        self.show_keys = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.keys_frame, text='Show keys', variable=self.show_keys,
                        command=self.toggle_keys).grid(row=len(KEYS), column=1, sticky='w', padx=10)
        ttk.Button(self.keys_frame, text='Save Keys', command=self.save_keys).grid(
            row=len(KEYS) + 1, column=0, columnspan=2, pady=20)

    def toggle_keys(self):
        for entry in self.key_entries.values():
            entry.config(show='' if self.show_keys.get() else '•')

    def save_keys(self):
        """Update the API keys in keys.txt, keeping any other settings already in the file."""
        values = {key: entry.get().strip() for key, entry in self.key_entries.items()}
        lines = KEY_FILE.read_text().splitlines() if KEY_FILE.exists() else []
        out = []
        for line in lines:
            name = line.split('=', 1)[0].strip()
            if name in values:
                out.append(f'{name}={values.pop(name)}')
            else:
                out.append(line)
        out += [f'{k}={v}' for k, v in values.items()]
        KEY_FILE.write_text('\n'.join(out) + '\n')
        messagebox.showinfo('Saved', 'API keys saved. Restart TypeGPT to use them.')

    def set_running(self, running, text=None):
        self.status_label.config(text=text or ('Status: Running' if running else 'Status: Not running'))
        self.start_button.config(state='disabled' if running else 'normal')
        self.stop_button.config(state='normal' if running else 'disabled')

    def start_program(self):
        if self.process:
            return
        try:
            self.process = subprocess.Popen([sys.executable, str(SCRIPT)], cwd=config.ROOT)
        except Exception as error:
            messagebox.showerror('Error', f'Failed to start TypeGPT: {error}')
            return
        self.set_running(True)
        self.master.after(1000, self.check_process)

    def check_process(self):
        if self.process and self.process.poll() is not None:
            code = self.process.returncode
            self.process = None
            self.set_running(False, None if code == 0 else f'Status: Exited (code {code}), see terminal')
        elif self.process:
            self.master.after(1000, self.check_process)

    def stop_program(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        self.set_running(False)

    def on_close(self):
        self.stop_program()
        self.master.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    TypeGPTGUI(root)
    root.mainloop()
