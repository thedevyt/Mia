import asyncio, os, threading
import tkinter as tk
from tkinter import ttk
from dotenv import load_dotenv
from ai_adapter.core.router import Router
from ai_adapter.core.executor import Executor
from ai_adapter.nlp.engines import make_engine
from ai_adapter.nlp.parser import SYSTEM_PROMPT
from ai_adapter.core.memory import Memory

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MIA – AI Adapter")
        self.geometry("900x560")

        self.memory = Memory()

        # --- Output text box ---
        self.txt = tk.Text(self, height=18, wrap="word")
        self.txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Input bar ---
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.entry = ttk.Entry(frm)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.focus_set()
        ttk.Button(frm, text="Send", command=self.on_send).pack(side=tk.LEFT, padx=6)
        self.status = ttk.Label(self, text="Ready")
        self.status.pack(fill=tk.X)

        # Bind the Return key (Enter) to send the command
        self.entry.bind("<Return>", self.on_enter)

        # --- Load environment and engines ---
        load_dotenv()
        self.engine = make_engine()
        intents_dir = os.path.join(os.path.dirname(__file__), "intents")
        self.router = Router(intents_dir)
        self.execu = Executor(confirm=os.getenv("CONFIRMATION", "ask") == "ask")

    # --- Utility logging ---
    def log(self, s: str):
        self.txt.insert(tk.END, s + "\n")
        self.txt.see(tk.END)

    # --- When user presses the Send button ---
    def on_send(self):
        text = self.entry.get().strip()
        self.entry.delete(0, tk.END)
        if not text:
            return
        self.log(f"You: {text}")
        threading.Thread(target=self._handle, args=(text,), daemon=True).start()

    # --- When user presses Enter ---
    def on_enter(self, event):
        self.on_send()
        return "break"  # prevent newline in entry field

    # --- Background handler for processing commands ---
    def _handle(self, text: str):
        self.status.config(text="Processing…")
        try:
            # --- Combine memory context + current user input ---
            context_prompt = self.memory.to_prompt()
            user_prompt = f"{context_prompt}\n\nUser: {text}" if context_prompt else text

            # --- Create a new event loop for this thread (Tkinter safe) ---
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            data = loop.run_until_complete(self.engine.parse(user_prompt, SYSTEM_PROMPT))
            loop.close()

            # --- Parse result from LLM ---
            if not isinstance(data, dict):
                self.log(f"Error: Invalid response from engine → {data}")
                return

            intent = data.get("intent")
            params = data.get("params", {})

            # --- Store in short-term memory ---
            self.memory.add(f"User: {text}")
            self.memory.add(f"MIA: {data}")

            # --- Update symbolic context for future prompts ---
            if intent == "create_folder" and "path" in params:
                self.memory.set("last_folder", params["path"])
            elif intent == "create_file" and "path" in params:
                self.memory.set("last_file", params["path"])
            elif intent == "edit_file" and "path" in params:
                self.memory.set("last_file", params["path"])

            # --- Execute the resulting intent ---
            spec = self.router.get(intent)
            cmds = self.execu.build(spec, params)
            for c in cmds:
                self.log(f"→ {c}")

            code = self.execu.run(cmds)
            self.log(f"✔ Exit code: {code}")

        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            self.status.config(text="Ready")


if __name__ == "__main__":
    App().mainloop()

