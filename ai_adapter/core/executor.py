from __future__ import annotations
import subprocess
import importlib
from typing import Dict, Any, List, Union
from jinja2 import Template
from rich import print


class Executor:
    def __init__(self, confirm: bool = True):
        self.confirm = confirm

    def _render(self, template: str, params: Dict[str, Any]) -> str:
        return Template(template).render(**(params or {}))

    def build(self, spec: Dict[str, Any], params: Dict[str, Any]) -> List[Union[str, dict]]:
        """
        Builds commands or plugin call specs depending on YAML intent type.
        """
        if "shell" in spec:
            return [self._render(cmd, params) for cmd in spec["shell"]]
        elif "plugin" in spec:
            return [{"plugin": spec["plugin"], "params": params}]
        raise ValueError("Spec missing shell list or plugin entry")

    def run(self, commands: List[Union[str, dict]]) -> int:
        """
        Executes shell commands or Python plugin functions.
        """
        code = 0
        for cmd in commands:
            if isinstance(cmd, str):
                # --- Shell command ---
                print(f"\n[bold]Will execute:[/bold] [cyan]{cmd}[/cyan]")
                if self.confirm:
                    ok = input("Execute? [y/N] ").strip().lower().startswith("y")
                    if not ok:
                        print("[yellow]Skipped.[/yellow]")
                        continue
                p = subprocess.run(cmd, shell=True)
                code = p.returncode

            elif isinstance(cmd, dict) and "plugin" in cmd:
                # --- Plugin call ---
                plugin_path = cmd["plugin"]
                params = cmd.get("params", {})
                try:
                    module_name, func_name = plugin_path.split(".")
                    mod = importlib.import_module(f"ai_adapter.plugins.{module_name}")
                    func = getattr(mod, func_name)
                    print(f"\n[magenta]→ Plugin call:[/magenta] {plugin_path} {params}")
                    code = func(**params)
                except Exception as e:
                    print(f"[red]❌ Plugin error:[/red] {e}")
                    code = 1

            else:
                print(f"[yellow]⚠️ Unknown command type:[/yellow] {cmd}")

        return code

