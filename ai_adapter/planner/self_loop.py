from __future__ import annotations

import sys
if __name__ == "__main__" and "ai_adapter.planner.self_loop" in sys.modules:
    del sys.modules["ai_adapter.planner.self_loop"]

import os
import io
import json
import asyncio
import contextlib
import subprocess
import shlex
import traceback
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from ai_adapter.core.router import Router
from ai_adapter.core.executor import Executor
from ai_adapter.core.memory import Memory
from ai_adapter.nlp.engines import make_engine
from ai_adapter.nlp.parser import SYSTEM_PROMPT



# ---------- SAFETY / CONFIG ----------
SAFE_INTENTS_DEFAULT = {
    "create_folder", "list_home", "list_dir",
    "create_file", "write_file", "edit_file", "read_file", "file_exists",
    "ping_host",
}

MAX_STEPS_DEFAULT = 20

def _needs_create(goal: str) -> bool:
    g = goal.lower()
    return any(w in g for w in (
        "create", "make", "write a file", "write file",
        "put a file", "add a file", "new folder", "new directory", "create folder"
    ))

def _needs_edit(goal: str) -> bool:
    g = goal.lower()
    return any(w in g for w in ("edit", "modify", "change", "convert", "update", "refactor"))

def _mentioned_path(goal: str) -> bool:
    # very light heuristic: goal mentions a path-ish token like ~/ or .py
    g = goal.lower()
    return ("~/" in g) or ("/home/" in g) or (".py" in g)

PLANNER_PROMPT = """
You are MIA's autonomous planner. You have to achieve the user's GOAL by deciding ONE next action
(intents are predefined). Think step-by-step but OUTPUT ONLY JSON with this schema:

{{
  "thought": "brief reasoning for the next action",
  "intent": "one_of_allowed_intents_or_null",
  "params": {{ ... }},
  "stop": false,
  "report": "1-2 sentence status update for the user"
}}

Rules:
- Choose only from ALLOWED_INTENTS (listed below).
- Only set "stop": true **after the last required action has been executed successfully**.
- If you still need to modify or verify something, first output the correct intent (e.g. edit_file or write_file) before stopping.
-Never stop immediately after reading; if you've read a file to inspect code, the next step must be an edit or write action.
- After reading a file, analyze its content and issue an edit_file intent next. Do not repeat read_file unless the file changed.
- Keep params minimal and accurate (expand "~" paths logically; use context when user says "in it").
- Never invent an intent.
- When you describe that something is created, you must also issue the actual action (e.g. create_file or write_file).
Do not mark stop=true until all required actions have been executed.
- If you cannot proceed safely, set "stop": true and explain in "report".

ALLOWED_INTENTS:
{allowed}

CONTEXT (symbolic):
{symbolic}

RECENT MESSAGES:
{history}

LAST OBSERVATION:
{observation}

GOAL:
{goal}
"""

# -------------------------------------

seen_actions = []
last_mutation = None 

@dataclass
class Observation:
    code: int = 0
    output: str = ""
    error: str = ""

def _expand(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))

def _capture_plugin_call(plugin_path: str, params: Dict[str, Any]) -> Observation:
    """
    Dynamically import and call a plugin, capturing printed output.
    Plugins typically return int exit codes; we capture prints to show the planner.
    """
    import importlib
    mod_name, func_name = plugin_path.split(".")
    mod = importlib.import_module(f"ai_adapter.plugins.{mod_name}")
    fn = getattr(mod, func_name)
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            code = fn(**params)
        except Exception as e:
            tb = traceback.format_exc()
            return Observation(code=1, output=buf.getvalue(), error=f"{e}\n{tb}")
    return Observation(code=code, output=buf.getvalue(), error="")

def _capture_shell(cmd: str) -> Observation:
    """
    Run a shell command and capture stdout/stderr safely.
    Expands ~ to the home folder to keep paths consistent.
    """
    try:
        cmd = os.path.expanduser(cmd)
        proc = subprocess.run(
            shlex.split(cmd),
            check=False,
            capture_output=True,
            text=True,
        )
        return Observation(code=proc.returncode, output=proc.stdout, error=proc.stderr)
    except Exception as e:
        return Observation(code=1, output="", error=str(e))

def _build_cmds(router: Router, spec: Dict[str, Any], params: Dict[str, Any]) -> List[Any]:
    """
    Build commands or plugin calls the same way the Executor does, but
    return them so we can capture output for the planner.
    """
    items: List[Any] = []
    if "shell" in spec:
        from jinja2 import Template
        for template in spec["shell"]:
            items.append(Template(template).render(**(params or {})))
    elif "plugin" in spec:
        items.append({"plugin": spec["plugin"], "params": params})
    else:
        raise ValueError("Spec missing shell list or plugin")
    return items

def _execute_and_observe(commands: List[Any]) -> Observation:
    """
    Execute a list of shell or plugin actions, capture all output and errors,
    and return a single aggregated Observation.
    """

    out_parts, err_parts = [], []
    code_final = 0

    for item in commands:
        # --- Execute shell or plugin call ---
        if isinstance(item, str):
            obs = _capture_shell(item)
        elif isinstance(item, dict) and "plugin" in item:
            obs = _capture_plugin_call(item["plugin"], item.get("params", {}))
        else:
            obs = Observation(code=1, output="", error=f"Unknown command type: {item!r}")

        # --- Always print the result so planner logs show real content ---
        if obs.output:
            print(obs.output.strip())  # ✅ makes plugin output visible to planner
            out_parts.append(obs.output.strip())

        if obs.error:
            print(f"[PLUGIN ERROR] {obs.error.strip()}")  # ✅ visible in logs
            err_parts.append(obs.error.strip())

        # track final return code
        code_final = obs.code

    # --- Combine results into one Observation ---
    aggregated_output = "\n".join(p for p in out_parts if p)
    aggregated_error = "\n".join(p for p in err_parts if p)

    return Observation(
        code=code_final,
        output=aggregated_output,
        error=aggregated_error,
    )


def _fmt_symbolic(mem: Memory) -> str:
    return mem.summary() or "(none)"

def _fmt_history(mem: Memory, max_lines: int = 12) -> str:
    txt = mem.context()
    if not txt:
        return "(none)"
    lines = txt.splitlines()[-max_lines:]
    return "\n".join(lines)

def safe_async_run(coro):
    """
    Run an async coroutine safely across multiple calls,
    avoiding 'Event loop is closed' or lingering httpx tasks.
    """
    import asyncio

    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        if "Event loop is closed" not in str(e):
            raise
    except KeyboardInterrupt:
        raise
    finally:
        try:
            # Create and close a fresh loop to clean up dangling tasks
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception:
            pass



@dataclass
class Planner:
    allowed_intents: set = field(default_factory=lambda: set(SAFE_INTENTS_DEFAULT))
    max_steps: int = MAX_STEPS_DEFAULT
    confirm: bool = False  # autonomous

    def run(self, goal: str) -> None:
        """
        Plan → Act → Observe → Repeat until done or max_steps reached.
        Prints a compact log to stdout.
        """
        router = Router(os.path.join(os.path.dirname(__file__), "..", "intents"))
        execu = Executor(confirm=self.confirm)
        engine = make_engine()
        memory = Memory()

        print(f"\n[PLANNER] Goal: {goal}\n[PLANNER] Allowed intents: {sorted(self.allowed_intents)}")
        observation = Observation(output="(start)", error="", code=0)
        seen_actions = []
        last_mutation = None

        for step in range(1, self.max_steps + 1):
            # Compose planner prompt
            prompt = PLANNER_PROMPT.format(
                allowed=", ".join(sorted(self.allowed_intents)),
                symbolic=_fmt_symbolic(memory),
                history=_fmt_history(memory),
                observation=(observation.output or observation.error or "(none)")[:2000],
                goal=goal,
            )

            # Ask LLM for next action
            data = safe_async_run(self._ask(engine, prompt))
            if not isinstance(data, dict):
                print(f"[PLANNER] Invalid planner JSON: {data}")
                break

            thought = data.get("thought", "")
            intent = data.get("intent")
            params = data.get("params", {}) or {}
            # Prevent infinite read loops by forcing an edit action next
            if intent == "read_file" and seen_actions.count("read_file") >= 1:
                print("[GUARD] Repeated read_file detected; forcing edit_file and stopping.")
                intent = "edit_file"
                stop = True
            # ----------------- GUARD: don't allow premature stop -----------------
            if data.get("stop", False):
                need_create = _needs_create(goal)
                need_edit   = _needs_edit(goal)

                MUTATION_INTENTS = {"create_file", "write_file", "edit_file", "create_folder"}

                did_create = any(a in MUTATION_INTENTS for a in seen_actions)
                did_edit   = any(a in ("edit_file", "write_file") for a in seen_actions)

                # If the goal clearly requires an edit/modify step, but none executed yet, keep going
                if need_edit and not did_edit:
                    print("[GUARD] 🟡 Goal requires editing but no edit/write action executed yet; continuing.")
                    stop = False
                # If the goal clearly requires creating/writing a file, but none executed yet, keep going
                elif need_create and not did_create:
                    print("[GUARD] 🟡 Goal requires creating/writing a file but no create/write action executed yet; continuing.")
                    stop = False
                else:
                    stop = True
            else:
                stop = False
            # --------------------------------------------------------------------
            report = data.get("report", "")

            print(f"\n[STEP {step}] thought: {thought}")
            if stop:
                print(f"[STEP {step}] stop=true — {report}")
                break

            if intent not in self.allowed_intents:
                print(f"[STEP {step}] ❌ intent '{intent}' not allowed. Stopping.")
                break

            # Update symbolic memory hints
            if intent in ("create_folder",) and "path" in params:
                memory.set("last_folder", params["path"])
            if intent in ("create_file", "write_file", "edit_file", "read_file", "file_exists") and "path" in params:
                # If "in it" cases were used, expand path using last_folder
                p = params["path"]
                if p.startswith("./") and memory.get("last_folder"):
                    params["path"] = os.path.join(memory.get("last_folder"), p[2:])
                memory.set("last_file", params["path"])

            # Build & execute
            try:
                spec = router.get(intent)
            except KeyError as e:
                print(f"[STEP {step}] ❌ Unknown intent: {e}")
                break

            cmds = _build_cmds(router, spec, params)
            print(f"[STEP {step}] action: {intent} params={params}")
            for c in cmds:
                print(f"   → {c}")

            observation = _execute_and_observe(cmds)
            seen_actions.append(intent)
            # append observation to rolling memory
            memory.add(f"MIA: ran {intent} params={params} -> code={observation.code}")
            if observation.output:
                memory.add(f"OBS: {observation.output[:500]}")
            if observation.error:
                memory.add(f"ERR: {observation.error[:500]}")

            # Simple success heuristic: if user goal mentions a file and it exists
            if "file" in goal.lower() and memory.get("last_file"):
                if os.path.exists(_expand(memory.get("last_file"))):
                    pass  # could set a completion signal here

        print("\n[PLANNER] loop finished.\n")

    async def _ask(self, engine, planner_prompt: str) -> Dict[str, Any]:
        """
        Ask your LLM with the planner prompt. We re-use your existing SYSTEM_PROMPT
        to force strict JSON, but feed the planner prompt as the 'user' content.
        """
        try:
            return await engine.parse(planner_prompt, SYSTEM_PROMPT)
        except Exception as e:
            return {"stop": True, "report": f"engine error: {e}"}


# --- CLI entrypoint ---
def main():
    import argparse
    p = argparse.ArgumentParser(description="MIA autonomous planner")
    p.add_argument("goal", help="Project goal in plain English")
    p.add_argument("--allow", nargs="*", default=None, help="Whitelist intents (overrides defaults)")
    p.add_argument("--steps", type=int, default=MAX_STEPS_DEFAULT, help="Max steps")
    p.add_argument("--confirm", action="store_true", help="Ask before each action (non-autonomous)")
    args = p.parse_args()

    allowed = set(args.allow) if args.allow else set(SAFE_INTENTS_DEFAULT)
    planner = Planner(allowed_intents=allowed, max_steps=args.steps, confirm=not not args.confirm)
    planner.run(args.goal)

if __name__ == "__main__":
    main()
