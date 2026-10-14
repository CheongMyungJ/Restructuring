"""Small I/O helpers: atomic JSON/text writes (safe against interruption and concurrent writers)."""
import json, os, tempfile, threading

_LOCK = threading.RLock()


def read_text(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return default


def write_text(path, text):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with _LOCK:
        fd, tmp = tempfile.mkstemp(dir=d, prefix='.tmp_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=1))
