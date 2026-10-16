"""Legacy Structure Similarity (LSS): how much a new implementation mirrors the STRUCTURE of the legacy code.

Behavior tests tell whether a redevelopment kept the behavior; this module tells whether it also copied the legacy
decomposition (files, functions, names, code shape) instead of being redesigned.  Deterministic, stdlib only.

Metrics (each 0..1, higher = closer to the legacy structure):
  M1 file_mirror      legacy source files that reappear in the new code: same normalized file name, or at least half
                      of the file's non-trivial functions mirrored into ONE new file (module boundary preserved)
  M2 name_reuse       legacy internal names (functions, types/classes, macros) defined again in the new code
  M3 clone_ratio      share of the new code's token 20-grams that also occur in the legacy code after renaming every
                      identifier/literal (copy-and-rename detection);  verbatim_ratio: same without renaming
  M4 function_mirror  legacy non-trivial functions that have a near-identical counterpart (normalized token 5-gram
                      Jaccard >= 0.5) in the new code, i.e. same function boundaries and same body shape
  LSS = 100 * mean(M1..M4).   Legacy vs itself = 100; an independent design scores low.

Contract files (e.g. a host API header the new code must keep byte-identical) are excluded on both sides and their
identifiers are not counted as reuse: preserving a contract is required, not structural dependence.
"""
import fnmatch, hashlib, os, re

CODE_EXT = {'.c': 'c', '.h': 'c', '.cc': 'c', '.cpp': 'c', '.cxx': 'c', '.hpp': 'c', '.hh': 'c',
            '.java': 'java', '.kt': 'java', '.scala': 'java', '.cs': 'java', '.go': 'c', '.rs': 'c',
            '.js': 'java', '.ts': 'java', '.py': 'py'}
SKIP_DIRS = {'.git', 'target', 'build', 'out', 'node_modules', '.gradle', '.idea', '.rekit', '__pycache__', 'test',
             'tests', 'testing'}
TEST_FILE = re.compile(r'(^test_|_test\.|^t_|Test\.java$|Tests\.java$|IT\.java$|^Test[A-Z])')
CONTROL = {'if', 'for', 'while', 'switch', 'catch', 'synchronized', 'return', 'sizeof', 'else', 'do', 'try',
           'new', 'throw', 'case', 'defined', 'elif', 'with', 'assert', 'typeof', 'alignof', '__attribute__'}
KEYWORDS = CONTROL | {
    'int', 'char', 'void', 'long', 'short', 'unsigned', 'signed', 'float', 'double', 'const', 'static', 'struct',
    'union', 'enum', 'typedef', 'extern', 'volatile', 'inline', 'register', 'break', 'continue', 'default', 'goto',
    'auto', 'bool', 'true', 'false', 'NULL', 'null', 'public', 'private', 'protected', 'class', 'interface',
    'extends', 'implements', 'final', 'abstract', 'package', 'import', 'this', 'super', 'boolean', 'byte',
    'throws', 'instanceof', 'var', 'let', 'function', 'def', 'self', 'None', 'True', 'False', 'and', 'or', 'not',
    'in', 'is', 'lambda', 'pass', 'yield', 'from', 'as', 'raise', 'except', 'finally', 'record', 'void',
    'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t', 'int8_t', 'int16_t', 'int32_t', 'int64_t', 'size_t'}
TOKEN_RE = re.compile(r'''
    (?P<str>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')
  | (?P<num>0[xX][0-9a-fA-F_]+[uUlL]*|\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?[uUlLfFdD]*)
  | (?P<id>[A-Za-z_$][A-Za-z0-9_$]*)
  | (?P<op>->|::|<<=|>>=|<<|>>|<=|>=|==|!=|&&|\|\||\+\+|--|[-+*/%&|^!~<>=?:;,.(){}\[\]@#])
''', re.X)
CLONE_K = 20
SHINGLE_K = 5
MIN_FUNC_TOKENS = 40
FUNC_MATCH = 0.5


def norm_name(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def strip_comments(text, lang):
    if lang == 'py':
        text = re.sub(r'(?m)^\s*#.*$', '', text)
        return re.sub(r'("""|\'\'\')[\s\S]*?\1', '""', text)
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            j = text.find('\n', i)
            i = n if j < 0 else j
        elif c == '/' and i + 1 < n and text[i + 1] == '*':
            j = text.find('*/', i + 2)
            seg = text[i:n if j < 0 else j + 2]
            out.append('\n' * seg.count('\n'))
            i = n if j < 0 else j + 2
        elif c in '"\'':
            m = re.compile(r'%s(?:\\.|[^%s\\\n])*%s' % (c, c, c)).match(text, i)
            if m:
                out.append(m.group(0)); i = m.end()
            else:
                out.append(c); i += 1
        else:
            out.append(c); i += 1
    return ''.join(out)


def tokenize(text):
    """[(kind, value)] with kind in str/num/id/op."""
    return [(m.lastgroup, m.group(m.lastgroup)) for m in TOKEN_RE.finditer(text)]


def normalized(tokens):
    """Identifiers -> ID, literals -> STR/NUM; keywords and operators kept (they carry the code's shape)."""
    out = []
    for k, v in tokens:
        if k == 'id':
            out.append(v if v in KEYWORDS else 'ID')
        elif k == 'str':
            out.append('STR')
        elif k == 'num':
            out.append('NUM')
        else:
            out.append(v)
    return out


def kgrams(seq, k):
    if len(seq) < k:
        return set()
    return {hashlib.blake2b(' '.join(seq[i:i + k]).encode(), digest_size=8).digest() for i in range(len(seq) - k + 1)}


class SourceFile:
    def __init__(self, root, rel):
        self.rel = rel
        self.lang = CODE_EXT[os.path.splitext(rel)[1].lower()]
        with open(os.path.join(root, rel), encoding='utf-8', errors='replace') as fh:
            raw = fh.read()
        text = strip_comments(raw, self.lang)
        self.defines = set(re.findall(r'(?m)^\s*#\s*define\s+([A-Za-z_]\w*)', text)) if self.lang == 'c' else set()
        if self.lang == 'c':
            text = re.sub(r'(?m)^\s*#.*(?:\\\n.*)*$', '', text)   # preprocessor lines (incl. continuations)
        self.tokens = tokenize(text)
        self.norm = normalized(self.tokens)
        self.loc = sum(1 for line in raw.splitlines() if line.strip())
        self.functions = self._functions(text)
        self.types = self._types()

    def _types(self):
        t, out = self.tokens, set()
        for i in range(len(t) - 1):
            if t[i][1] in ('struct', 'union', 'enum', 'class', 'interface', 'record') and t[i + 1][0] == 'id':
                out.add(t[i + 1][1])
        if self.lang == 'c':      # typedef ... NAME ;
            for i, (k, v) in enumerate(t):
                if v == 'typedef':
                    depth, j = 0, i + 1
                    while j < len(t) and not (t[j][1] == ';' and depth == 0):
                        depth += t[j][1] in '({[' and t[j][0] == 'op'
                        depth -= t[j][1] in ')}]' and t[j][0] == 'op'
                        j += 1
                    k2 = j - 1
                    while k2 > i and t[k2][1] in (')', ']') or (k2 > i and t[k2][0] == 'num'):
                        k2 -= 1
                    if k2 > i and t[k2][0] == 'id':
                        out.add(t[k2][1])
        return out

    def _functions(self, text):
        """[(name, normalized body tokens)] for every function/method with a body."""
        if self.lang == 'py':
            return self._py_functions(text)
        t, funcs, i, n = self.tokens, [], 0, len(self.tokens)
        while i < n:
            if t[i] == ('op', '{') and self._is_func_open(i):
                name = self._func_name(i)
                depth, j = 0, i
                while j < n:
                    if t[j] == ('op', '{'):
                        depth += 1
                    elif t[j] == ('op', '}'):
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                if name:
                    funcs.append((name, normalized(t[i:j + 1])))
                i = j + 1
                continue
            i += 1
        return funcs

    def _close_paren_before(self, i):
        """Index of the ')' that ends a signature right before '{' at i (skipping throws/const/annotations)."""
        t, j = self.tokens, i - 1
        while j >= 0 and t[j][1] != ')':
            if t[j][1] in (';', '{', '}', '=', '->', ']') or t[j][0] in ('str', 'num'):
                return None
            if t[j][1] not in ('throws', 'const', 'noexcept', 'override', ',', '.') and t[j][0] != 'id':
                return None
            j -= 1
        return j if j >= 0 else None

    def _is_func_open(self, i):
        return self._func_name(i) is not None

    def _func_name(self, i):
        t = self.tokens
        j = self._close_paren_before(i)
        if j is None:
            return None
        depth = 0
        while j >= 0:
            if t[j][1] == ')':
                depth += 1
            elif t[j][1] == '(':
                depth -= 1
                if depth == 0:
                    break
            j -= 1
        if j <= 0 or t[j - 1][0] != 'id' or t[j - 1][1] in CONTROL:
            return None
        if j >= 2 and t[j - 2][1] in ('new', '.', '->'):
            return None
        return t[j - 1][1]

    def _py_functions(self, text):
        lines = text.splitlines()
        funcs, i = [], 0
        while i < len(lines):
            m = re.match(r'^(\s*)def\s+(\w+)\s*\(', lines[i])
            if m:
                ind, j = len(m.group(1)), i + 1
                while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > ind):
                    j += 1
                funcs.append((m.group(2), normalized(tokenize('\n'.join(lines[i:j])))))
                i = j
                continue
            i += 1
        return funcs


def collect(root, contract_globs=(), exclude_tests=True):
    files, contract = [], []
    for dp, dn, fs in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS and not d.startswith('.'))
        for f in sorted(fs):
            if os.path.splitext(f)[1].lower() not in CODE_EXT:
                continue
            rel = os.path.relpath(os.path.join(dp, f), root).replace(os.sep, '/')
            if exclude_tests and TEST_FILE.search(f):
                continue
            if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(f, g) for g in contract_globs):
                contract.append(rel)
                continue
            files.append(rel)
    return files, contract


def contract_identifiers(root, rels):
    ids = set()
    for rel in rels:
        sf = SourceFile(root, rel)
        ids |= {v for k, v in sf.tokens if k == 'id'} | sf.defines
    return ids


def compare(legacy_root, new_root, contract_globs=(), detail=False):
    """Structural similarity of new_root to legacy_root. Contract globs match paths (or basenames) on both sides."""
    lfiles, lcontract = collect(legacy_root, contract_globs)
    nfiles, ncontract = collect(new_root, contract_globs)
    L = [SourceFile(legacy_root, r) for r in lfiles]
    N = [SourceFile(new_root, r) for r in nfiles]
    cids = {norm_name(x) for x in contract_identifiers(legacy_root, lcontract)}

    # M3 clone ratio over whole token streams
    lk = set().union(*(kgrams(f.norm, CLONE_K) for f in L)) if L else set()
    nk_list = [kgrams(f.norm, CLONE_K) for f in N]
    nk = set().union(*nk_list) if nk_list else set()
    clone = len(nk & lk) / len(nk) if nk else 0.0
    lv = set().union(*(kgrams([v for _, v in f.tokens], CLONE_K) for f in L)) if L else set()
    nv = set().union(*(kgrams([v for _, v in f.tokens], CLONE_K) for f in N)) if N else set()
    verbatim = len(nv & lv) / len(nv) if nv else 0.0

    # M4 function mirror
    lfun = [(f.rel, name, kgrams(body, SHINGLE_K)) for f in L for name, body in f.functions
            if len(body) >= MIN_FUNC_TOKENS]
    nfun = [(f.rel, name, kgrams(body, SHINGLE_K)) for f in N for name, body in f.functions
            if len(body) >= MIN_FUNC_TOKENS // 2]
    mirrored = []          # (legacy file, legacy fn, new file, new fn, jaccard)
    for lrel, lname, ls in lfun:
        best, bj = None, 0.0
        if ls:
            for nrel, nname, ns in nfun:
                if not ns:
                    continue
                inter = len(ls & ns)
                if inter == 0:
                    continue
                j = inter / len(ls | ns)
                if j > bj:
                    best, bj = (nrel, nname), j
        if best and bj >= FUNC_MATCH:
            mirrored.append((lrel, lname, best[0], best[1], round(bj, 3)))
    fmirror = len(mirrored) / len(lfun) if lfun else 0.0

    # M1 file mirror: same normalized stem, or >= half of the file's functions mirrored into one new file
    nstems = {norm_name(os.path.splitext(os.path.basename(f.rel))[0]) for f in N}
    by_lfile = {}
    for lrel, _, _ in lfun:
        by_lfile.setdefault(lrel, 0)
        by_lfile[lrel] += 1
    targets = {}
    for lrel, _, nrel, _, _ in mirrored:
        targets.setdefault(lrel, {}).setdefault(nrel, 0)
        targets[lrel][nrel] += 1
    file_rows = []
    for f in L:
        if not f.functions and not f.types and not f.defines:
            continue
        stem = norm_name(os.path.splitext(os.path.basename(f.rel))[0])
        by_name = stem in nstems and len(stem) >= 3
        tot = by_lfile.get(f.rel, 0)
        best_target = max(targets.get(f.rel, {}).items(), key=lambda kv: kv[1], default=(None, 0))
        by_content = tot >= 1 and best_target[1] * 2 >= tot
        file_rows.append({'file': f.rel, 'by_name': by_name, 'by_content': by_content,
                          'target': best_target[0] if by_content else None})
    fm = sum(1 for r in file_rows if r['by_name'] or r['by_content']) / len(file_rows) if file_rows else 0.0

    # M2 internal name reuse (definitions only)
    def defined(files):
        out = set()
        for f in files:
            out |= {n for n, _ in f.functions} | f.types | f.defines
        return {norm_name(x) for x in out if len(x) >= 4}
    lnames = defined(L) - cids
    nnames = defined(N)
    reused = sorted(lnames & nnames)
    reuse = len(reused) / len(lnames) if lnames else 0.0

    res = {
        'LSS': round(100 * (fm + reuse + clone + fmirror) / 4, 1),
        'M1_file_mirror': round(fm, 3), 'M2_name_reuse': round(reuse, 3), 'M3_clone_ratio': round(clone, 3),
        'M4_function_mirror': round(fmirror, 3), 'verbatim_ratio': round(verbatim, 3),
        'legacy': {'files': len(L), 'loc': sum(f.loc for f in L), 'functions': len(lfun), 'names': len(lnames),
                   'contract_files': lcontract},
        'new': {'files': len(N), 'loc': sum(f.loc for f in N),
                'functions': sum(1 for f in N for _, b in f.functions if len(b) >= MIN_FUNC_TOKENS),
                'contract_files': ncontract},
    }
    if detail:
        res['detail'] = {'mirrored_functions': mirrored, 'files': file_rows, 'reused_names': reused}
    return res


def format_report(r):
    lines = [f"LSS (레거시 구조 유사도) {r['LSS']}/100   — 낮을수록 레거시 구조에서 독립",
             f"  M1 파일 대응률      {r['M1_file_mirror']:.1%}",
             f"  M2 내부 이름 재사용 {r['M2_name_reuse']:.1%}",
             f"  M3 구조 클론률      {r['M3_clone_ratio']:.1%}   (원문 그대로 {r['verbatim_ratio']:.1%})",
             f"  M4 함수 대응률      {r['M4_function_mirror']:.1%}",
             f"  레거시 {r['legacy']['files']}파일/{r['legacy']['loc']}LOC/함수 {r['legacy']['functions']}  →  "
             f"신규 {r['new']['files']}파일/{r['new']['loc']}LOC/함수 {r['new']['functions']}"]
    if r['legacy']['contract_files']:
        lines.append(f"  계약 파일(제외): {', '.join(r['legacy']['contract_files'])}")
    return '\n'.join(lines)


TARGET_LSS, TARGET_M4 = 20.0, 0.10


def kit_contract_globs(script_path):
    """When shipped as kit/tools/structure_check.py, the contract files are the kit's verbatim copies in
    kit/03_interfaces/files/ — fixed by the kit, not chosen by the implementer."""
    files = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(script_path))), '03_interfaces', 'files')
    out = []
    for dp, _, fs in os.walk(files):
        for f in fs:
            out.append(os.path.relpath(os.path.join(dp, f), files).replace(os.sep, '/'))
    return sorted(out)


def verdict(r):
    ok = r['LSS'] < TARGET_LSS and r['M4_function_mirror'] < TARGET_M4
    return (f"판정: {'통과' if ok else '미달'} (목표 LSS < {TARGET_LSS:.0f} 그리고 함수 대응률 M4 < {TARGET_M4:.0%}; "
            f"이름만 바꾸는 것으로는 M3·M4가 줄지 않는다 — 대응 함수는 design/ 에 따라 다시 작성)")


def main(argv=None):
    """Standalone use (the kit ships this file as tools/structure_check.py):
    python3 structure_check.py <legacy_code_dir> <new_code_dir> [--contract GLOB ...] [--json] [--detail]
    Inside a kit, the official result always uses the kit's contract files (03_interfaces/files/); extra --contract
    globs only produce an additional, clearly labelled reference figure."""
    import argparse, json
    ap = argparse.ArgumentParser(description='Legacy Structure Similarity (LSS): 0 = independent, 100 = copy of legacy')
    ap.add_argument('legacy'); ap.add_argument('new')
    ap.add_argument('--contract', action='append', default=[], help='contract file glob kept unchanged on purpose')
    ap.add_argument('--json', action='store_true'); ap.add_argument('--detail', action='store_true')
    a = ap.parse_args(argv)
    kit = kit_contract_globs(__file__) if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' else []
    official = kit or a.contract
    r = compare(a.legacy, a.new, official, detail=a.detail)
    extra = [c for c in a.contract if c not in official]
    if a.json:
        if extra:
            r['reference_with_extra_contracts'] = {k: v for k, v in compare(a.legacy, a.new, official + extra).items()
                                                   if k != 'detail'}
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if kit:
        print(f"계약 파일(키트 03_interfaces/files 기준, 고정): {len(kit)}개")
    print(format_report(r))
    print(verdict(r))
    if extra:
        x = compare(a.legacy, a.new, official + extra)
        print(f"\n[참고용, 판정에 쓰지 않음] 추가 제외 {extra} 적용 시 LSS {x['LSS']} — 키트가 계약으로 정하지 않은 "
              f"파일을 제외하면 구조 유사도가 가려진다")
    if a.detail:
        print('\n레거시와 대응하는 함수 (레거시 파일:함수 -> 신규 파일:함수, 유사도):')
        for lf, ln, nf, nn, j in sorted(r['detail']['mirrored_functions']):
            print(f'  {lf}:{ln} -> {nf}:{nn}  {j}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
