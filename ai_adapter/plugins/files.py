"""
MIA Plugin – File operations
Supports:
  • create_file(path, content)
  • write_file(path, content, mode="overwrite"|"append")
  • edit_file(path, new_content, start_marker=None, end_marker=None, keyword=None)

Each function returns 0 on success, 1 on error.
"""

import os
from typing import Optional
from rich import print


def _expand(path: str) -> str:
    """Expand environment variables and ~ in paths."""
    path = os.path.expandvars(path)       # expands $USER, $HOME, etc.
    path = os.path.expanduser(path)       # expands ~
    return os.path.abspath(path)

def _preview_change(path: str, before: str, after: str) -> None:
    """Print a short diff-style preview of what changed."""
    try:
        import difflib
        diff = difflib.unified_diff(
            before.splitlines(), after.splitlines(),
            fromfile="before", tofile="after", lineterm=""
        )
        lines = list(diff)
        if lines:
            print("[yellow]🟡 Preview of changes:[/yellow]")
            for d in lines[:15]:
                print(d)
            if len(lines) > 15:
                print("[dim]…diff truncated…[/dim]")
    except Exception:
        pass


# ------------------------------------------------------------
# 1️⃣  CREATE NEW FILE
# ------------------------------------------------------------
def create_file(path: str, content: str = "") -> int:
    """Create a new file with optional text content."""
    try:
        path = _expand(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content or "")
        print(f"[green]✅ Created file:[/green] {path}")
        return 0
    except Exception as e:
        print(f"[red]❌ create_file error:[/red] {e}")
        return 1


# ------------------------------------------------------------
# 2️⃣  WRITE OR OVERWRITE WHOLE FILE
# ------------------------------------------------------------
def write_file(path: str, content: str, mode: str = "overwrite") -> int:
    """Write or append to an entire file."""
    try:
        path = _expand(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_mode = "a" if mode == "append" else "w"
        with open(path, write_mode, encoding="utf-8") as f:
            f.write(content)
        action = "Appended to" if write_mode == "a" else "Overwrote"
        print(f"[green]✅ {action}:[/green] {path}")
        return 0
    except Exception as e:
        print(f"[red]❌ write_file error:[/red] {e}")
        return 1


# ------------------------------------------------------------
# 3️⃣  EDIT ONLY PART OF A FILE
# ------------------------------------------------------------
def edit_file(
    path: str,
    new_content: str,
    start_marker: Optional[str] = None,
    end_marker: Optional[str] = None,
    keyword: Optional[str] = None,
) -> int:
    """
    Replace a section of a file.

    Modes:
      - start_marker + end_marker → replace everything between them (keep markers)
      - keyword → replace the line OR entire function/class block containing it
      - none → replace the whole file

    Returns 0 on success, 1 on failure.
    """
    import shutil, difflib, re

    try:
        path = _expand(path)
        if not os.path.exists(path):
            print(f"[red]❌ File not found:[/red] {path}")
            return 1

        with open(path, "r", encoding="utf-8") as f:
            before = f.read()

        # Backup
        try:
            shutil.copy2(path, path + ".bak")
            print(f"[dim]🗂️  Backup created:[/dim] {path}.bak")
        except Exception as e:
            print(f"[yellow]⚠️ Backup failed:[/yellow] {e}")

        edited = before
        replaced = False

        # 1️⃣  Marker-based
        if start_marker and end_marker:
            pattern = re.compile(
                re.escape(start_marker) + r"(.*?)" + re.escape(end_marker),
                re.DOTALL,
            )
            edited, n = pattern.subn(
                start_marker + "\n" + new_content.rstrip() + "\n" + end_marker,
                before,
            )
            replaced = n > 0

        # 2️⃣  Keyword-based (replace full function/class block)
        elif keyword:
            block_pattern = (
                rf"(^[ \t]*@.*\n)*"  # decorators
                rf"^[ \t]*(async[ \t]+)?(def|class)[ \t]+{re.escape(keyword.strip().split('(')[0])}\b"
                r".*?(?=^[ \t]*(?:def|class|@|\Z))"
            )
            match = re.search(block_pattern, before, flags=re.DOTALL | re.MULTILINE)
            if match:
                # Detect indentation of the original block
                first_line = before.splitlines()[match.start(0):match.end(0)][0]
                indent_match = re.match(r"^([ \t]*)", first_line)
                base_indent = indent_match.group(1) if indent_match else ""

                # Normalize new content indentation
                normalized = []
                for line in new_content.splitlines():
                    if line.strip():  # non-empty
                        normalized.append(base_indent + line.lstrip())
                    else:
                        normalized.append("")
                fixed_content = "\n".join(normalized) + "\n"

                edited = before[:match.start()] + fixed_content + before[match.end():]
                replaced = True
            else:
                # safer single-line keyword replace (anchors full line)
                pattern = rf"^[ \t]*{re.escape(keyword)}[ \t]*$"
                edited, n = re.subn(pattern, new_content, before, flags=re.MULTILINE)
                replaced = n > 0

        # 3️⃣  Default: overwrite entire file (safe fallback)
        else:
            # Overwrite the entire file with new_content cleanly
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content.rstrip() + "\n")
            print(f"[green]✅ Overwrote entire file:[/green] {path}")
            return 0


        # --- Diff preview ---
        diff = list(
            difflib.unified_diff(
                before.splitlines(),
                edited.splitlines(),
                fromfile="before",
                tofile="after",
                lineterm=""
            )
        )
        if diff:
            print("[yellow]🟡 Preview of changes:[/yellow]")
            for d in diff[:20]:
                print(d)
            if len(diff) > 20:
                print("[dim]…diff truncated…[/dim]")

        with open(path, "w", encoding="utf-8") as f:
            f.write(edited)

        if replaced:
            print(f"[green]✅ Edited file successfully:[/green] {path}")
            return 0

        print(f"[yellow]⚠️ No match found for keyword or markers in:[/yellow] {path}")
        return 1

    except Exception as e:
        print(f"[red]❌ edit_file error:[/red] {e}")
        return 1

def read_file(path: str):
    """
    Print file contents so the planner can observe them.
    """
    import os
    path = os.path.expanduser(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        print(content)
        return 0
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return 1


def file_exists(path: str) -> bool:
    """Return True if file exists."""
    return os.path.exists(_expand(path))

def create_folder(path: str) -> int:
    """
    Create a folder at the given path (supports ~) and open it in the file manager.
    Returns 0 on success, 1 on failure.
    """
    try:
        path = _expand(path)
        os.makedirs(path, exist_ok=True)

        print(f"[green]✅ Created folder:[/green] {path}")

        # open in system file manager (async, doesn't block MIA)
        os.system(f"xdg-open '{path}' &")

        return 0
    except Exception as e:
        print(f"[red]❌ create_folder error:[/red] {e}")
        return 1

def list_dir(path: str):
    """
    List contents of a specific directory path.
    """
    import os, subprocess
    target = os.path.expanduser(path)
    try:
        print(subprocess.getoutput(f"ls -lah {target}"))
        return 0
    except Exception as e:
        print(f"Error listing {target}: {e}")
        return 1

