"""Deterministic inventory of legacy code: file classification, size, language, symbols (heuristic)."""
import hashlib, json, os, re

SKIP_DIRS = {'.git', '.svn', '.hg', 'node_modules', 'target', 'build', 'dist', 'out', 'bin-debug', '.idea',
             '.vscode', '__pycache__', '.gradle', '.settings', 'CVS', '.rekit'}
LANG_BY_EXT = {
    '.c': 'c', '.h': 'c-header', '.cc': 'cpp', '.cpp': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp-header', '.hh': 'cpp-header',
    '.s': 'asm', '.S': 'asm', '.asm': 'asm', '.inc': 'asm-include', '.ld': 'linker-script', '.lds': 'linker-script',
    '.java': 'java', '.kt': 'kotlin', '.scala': 'scala', '.groovy': 'groovy', '.jsp': 'jsp', '.jspf': 'jsp', '.tag': 'jsp',
    '.xml': 'xml', '.xsd': 'xml', '.wsdl': 'xml', '.properties': 'properties', '.yml': 'yaml', '.yaml': 'yaml',
    '.json': 'json', '.sql': 'sql', '.ddl': 'sql', '.pls': 'plsql', '.pck': 'plsql', '.pkb': 'plsql', '.pks': 'plsql',
    '.prc': 'plsql', '.fnc': 'plsql', '.trg': 'plsql', '.pc': 'proc-c', '.sh': 'shell', '.bash': 'shell', '.ksh': 'shell',
    '.csh': 'shell', '.bat': 'batch', '.cmd': 'batch', '.ps1': 'powershell', '.py': 'python', '.pl': 'perl', '.pm': 'perl',
    '.rb': 'ruby', '.php': 'php', '.js': 'javascript', '.ts': 'typescript', '.jsx': 'javascript', '.tsx': 'typescript',
    '.html': 'html', '.htm': 'html', '.css': 'css', '.go': 'go', '.rs': 'rust', '.cs': 'csharp', '.vb': 'vbnet',
    '.bas': 'vb6', '.frm': 'vb6', '.cls': 'vb6', '.ctl': 'vb6', '.vbp': 'vb6-project', '.pas': 'pascal', '.dpr': 'pascal',
    '.dfm': 'delphi-form', '.srw': 'powerbuilder', '.sru': 'powerbuilder', '.srd': 'powerbuilder', '.srf': 'powerbuilder',
    '.cbl': 'cobol', '.cob': 'cobol', '.cpy': 'cobol-copybook', '.jcl': 'jcl', '.pli': 'pli', '.f': 'fortran',
    '.f90': 'fortran', '.for': 'fortran', '.v': 'verilog', '.sv': 'systemverilog', '.vhd': 'vhdl', '.vhdl': 'vhdl',
    '.tcl': 'tcl', '.mk': 'makefile', '.cmake': 'cmake', '.gradle': 'gradle', '.ini': 'ini', '.cfg': 'config',
    '.conf': 'config', '.toml': 'toml', '.csv': 'data-csv', '.txt': 'text', '.md': 'markdown', '.rst': 'text',
}
NAME_LANG = {'makefile': 'makefile', 'gnumakefile': 'makefile', 'cmakelists.txt': 'cmake', 'pom.xml': 'maven',
             'build.gradle': 'gradle', 'dockerfile': 'docker', 'kconfig': 'kconfig', 'sconstruct': 'scons'}
BUILD_FILES = {'makefile', 'gnumakefile', 'cmakelists.txt', 'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle',
               'build.xml', 'package.json', 'go.mod', 'cargo.toml', 'setup.py', 'pyproject.toml', 'sconstruct',
               'build.sh', 'meson.build', '.project', '.cproject', 'kconfig'}
VENDOR_HINTS = re.compile(r'(^|/)(vendor|third[_-]?party|external|extern|lib/[^/]+\.jar|bsp|sdk|xilinx|cmsis|hal_driver|'
                          r'generated|gen-src|autogen)(/|$)', re.I)

C_FUNC = re.compile(r'^[A-Za-z_][\w \t\*]*?\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{', re.M)
JAVA_TYPE = re.compile(r'\b(class|interface|enum)\s+([A-Z]\w*)')
JAVA_METHOD = re.compile(r'^\s*(public|protected|private|static|final|synchronized|\s)*[\w<>\[\],\s]+\s+([a-z]\w*)\s*\([^;]*\)\s*(throws [\w.,\s]+)?\{', re.M)
SQL_ID = re.compile(r'<(select|insert|update|delete|sql)\s+id="([^"]+)"', re.I)
C_KEYWORDS = {'if', 'for', 'while', 'switch', 'return', 'sizeof', 'else', 'do'}


def is_binary(path, nbytes=4096):
    try:
        with open(path, 'rb') as f:
            chunk = f.read(nbytes)
        if b'\0' in chunk:
            return True
        return False
    except OSError:
        return True


def detect_lang(rel):
    base = os.path.basename(rel).lower()
    if base in NAME_LANG:
        return NAME_LANG[base]
    ext = os.path.splitext(rel)[1]
    return LANG_BY_EXT.get(ext, LANG_BY_EXT.get(ext.lower(), 'other'))


def read_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in ('utf-8', 'cp949', 'euc-kr', 'latin-1'):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1', 'replace'), 'latin-1'


def symbols_for(lang, text):
    syms = []
    if lang in ('c', 'cpp', 'proc-c'):
        syms = [m.group(1) for m in C_FUNC.finditer(text) if m.group(1) not in C_KEYWORDS]
    elif lang in ('java', 'kotlin', 'scala', 'groovy'):
        syms = [m.group(2) for m in JAVA_TYPE.finditer(text)] + \
               [m.group(2) for m in JAVA_METHOD.finditer(text) if m.group(2) not in C_KEYWORDS]
    elif lang == 'xml':
        syms = [m.group(2) for m in SQL_ID.finditer(text)]
    return sorted(set(syms))[:400]


def scan(code_roots):
    """Return inventory dict: files list + aggregates. code_roots: list of (label, abs_path)."""
    files = []
    for label, root in code_roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.'))
            for fn in sorted(filenames):
                ap = os.path.join(dirpath, fn)
                rel = os.path.relpath(ap, root)
                if os.path.islink(ap):
                    continue
                size = os.path.getsize(ap)
                entry = {'root': label, 'path': rel, 'bytes': size, 'lang': detect_lang(rel)}
                if is_binary(ap) or size > 5_000_000:
                    entry.update(kind='binary', loc=0, tokens=0)
                else:
                    text, enc = read_text(ap)
                    lines = text.splitlines()
                    entry.update(kind='text', encoding=enc, loc=sum(1 for l in lines if l.strip()),
                                 lines=len(lines), tokens=int(len(text.encode('utf-8')) / 3.6),
                                 sha1=hashlib.sha1(text.encode('utf-8', 'replace')).hexdigest()[:12],
                                 symbols=symbols_for(entry['lang'], text))
                entry['build_file'] = fn.lower() in BUILD_FILES
                entry['vendor_hint'] = bool(VENDOR_HINTS.search(rel.replace(os.sep, '/')))
                files.append(entry)
    langs = {}
    for f in files:
        l = langs.setdefault(f['lang'], {'files': 0, 'loc': 0, 'tokens': 0})
        l['files'] += 1
        l['loc'] += f.get('loc', 0)
        l['tokens'] += f.get('tokens', 0)
    return {
        'files': files,
        'totals': {'files': len(files), 'loc': sum(f.get('loc', 0) for f in files),
                   'tokens': sum(f.get('tokens', 0) for f in files)},
        'languages': dict(sorted(langs.items(), key=lambda kv: -kv[1]['loc'])),
        'build_files': [f"{f['root']}:{f['path']}" for f in files if f['build_file']],
    }


def tree_summary(inv, max_lines=400):
    """Compact directory listing with LOC for prompts."""
    out = []
    for f in inv['files']:
        tag = ' [vendor?]' if f.get('vendor_hint') else ''
        tag += ' [binary]' if f['kind'] == 'binary' else ''
        out.append(f"{f['root']}:{f['path']}  ({f['lang']}, {f.get('loc', 0)} loc, ~{f.get('tokens', 0)} tok){tag}")
    if len(out) > max_lines:
        dirs = {}
        for f in inv['files']:
            d = f['root'] + ':' + os.path.dirname(f['path'])
            x = dirs.setdefault(d, [0, 0, 0]); x[0] += 1; x[1] += f.get('loc', 0); x[2] += f.get('tokens', 0)
        out = [f"{d}/  ({v[0]} files, {v[1]} loc, ~{v[2]} tok)" for d, v in sorted(dirs.items())]
    return '\n'.join(out)
