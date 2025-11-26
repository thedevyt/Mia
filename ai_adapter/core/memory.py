from collections import deque
import os

class Memory:
    """Rolling conversational memory with symbolic context (paths, vars)."""
    def __init__(self, maxlen: int = 20):
        self.buf = deque(maxlen=maxlen)
        self.state = {}

    # -------------------------------
    # Conversation memory
    # -------------------------------
    def add(self, text: str):
        """Add a user or assistant message to the rolling chat context."""
        self.buf.append(text)

    def context(self) -> str:
        """Return recent conversation history for the LLM."""
        if not self.buf:
            return ""
        return "\n".join(self.buf)

    # -------------------------------
    # Symbolic context (folders/files)
    # -------------------------------
    def set(self, key: str, value: str):
        self.state[key] = os.path.expanduser(value)

    def get(self, key: str, default=None):
        return self.state.get(key, default)

    def summary(self) -> str:
        """Compact text summary for inclusion in prompts."""
        if not self.state:
            return ""
        lines = [f"- {k}: {v}" for k, v in self.state.items()]
        return "Context:\n" + "\n".join(lines)

    # -------------------------------
    # Combined prompt context
    # -------------------------------
    def to_prompt(self) -> str:
        """
        Combine structured context (last file/folder)
        with last conversation messages.
        """
        ctx = []
        if self.state:
            ctx.append(self.summary())
        if self.buf:
            ctx.append("\nRecent conversation:\n" + self.context())
        return "\n".join(ctx).strip()

