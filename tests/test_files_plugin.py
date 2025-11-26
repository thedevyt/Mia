import os
import tempfile

from ai_adapter.plugins import files


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_edit_file_replaces_decorated_function_block():
    original = """\
@decorator
async def target(x):
    return x + 1

def untouched():
    return 0
"""
    replacement = """\
async def target(y):
    return y * 2
"""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "demo.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(original)

        code = files.edit_file(path=path, new_content=replacement, keyword="target")
        assert code == 0
        after = _read(path)

        assert "decorator" not in after  # decorator removed along with block
        assert "return y * 2" in after
        assert "untouched" in after


def test_edit_file_single_line_fallback_is_anchored():
    original = """\
value = "keyword should not change inside strings"
keyword
"""
    replacement = "keyword = 42"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "demo.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(original)

        code = files.edit_file(path=path, new_content=replacement, keyword="keyword")
        assert code == 0
        after = _read(path)

        # Inline string remains untouched
        assert 'keyword should not change inside strings' in after
        # Only the standalone line was replaced
        assert "keyword = 42" in after
        assert after.count("keyword") == 1
