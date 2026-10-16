"""Offline tests for the Legacy Structure Similarity metric. Run: python3 -m unittest discover -s tests"""
import os, re, shutil, sys, tempfile, unittest

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ENGINE)
from rekit import similarity  # noqa: E402

API_H = 'typedef struct { int op; int lba; } cmd_t;\nint fw_submit(const cmd_t *c);\n'
GC_C = '''#include "api.h"
static int g_valid[64];
int gc_select_victim(int nblk)
{
    int best = -1, i, min = 1 << 30;
    for (i = 0; i < nblk; i++) {
        if (g_valid[i] < min && g_valid[i] >= 0) { min = g_valid[i]; best = i; }
        else if (g_valid[i] == min && best > i) { best = i; }
    }
    return best;
}
int gc_run_one(int nblk)
{
    int v = gc_select_victim(nblk);
    if (v < 0) return -1;
    g_valid[v] = 0;
    for (int p = 0; p < 16; p++) { if (p % 3 == 0) g_valid[v] += 1; else g_valid[v] -= 0; }
    return v;
}
'''
HOST_C = '''#include "api.h"
int gc_run_one(int nblk);
int fw_submit(const cmd_t *c)
{
    switch (c->op) {
    case 1: if (c->lba > 100) return 2; return gc_run_one(c->lba);
    case 2: { int s = 0; for (int i = 0; i < c->lba; i++) s += i * 3; return s; }
    default: return 1;
    }
}
'''
# an independent design: one pool object, different decomposition and shapes
POOL_C = '''#include "api.h"
#define POOL_MAX 64
typedef struct { unsigned valid[POOL_MAX]; unsigned count; } block_pool;
static block_pool pool = { {0}, POOL_MAX };
static unsigned pool_score(const block_pool *p, unsigned b) { return p->valid[b] * 2u + b; }
unsigned pool_pick(const block_pool *p)
{
    unsigned b = 0, chosen = 0, s, lowest = ~0u;
    while (b < p->count) { s = pool_score(p, b); chosen = s < lowest ? b : chosen; lowest = s < lowest ? s : lowest; ++b; }
    return chosen;
}
int fw_submit(const cmd_t *c)
{
    static int (*const table[3])(const cmd_t *) = { 0 };
    if (c->op < 0 || c->op > 2 || !table[c->op]) return c->op == 1 ? (int)pool_pick(&pool) : 1;
    return table[c->op](c);
}
'''


def write(root, files):
    for rel, text in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w').write(text)


class SimilarityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='rekit_sim_')
        self.legacy = os.path.join(self.tmp, 'legacy_code')
        write(self.legacy, {'api.h': API_H, 'ftl/ftl_gc.c': GC_C, 'host/host.c': HOST_C})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_self_is_100(self):
        r = similarity.compare(self.legacy, self.legacy, ['api.h'])
        self.assertEqual(r['LSS'], 100.0)
        self.assertEqual(r['legacy']['contract_files'], ['api.h'])

    def test_renamed_port_still_detected(self):
        new = os.path.join(self.tmp, 'new')
        ren = lambda t: re.sub(r'\bg_valid\b', 'valid_cnt', t.replace('gc_select_victim', 'pick_block')
                               .replace('gc_run_one', 'collect_once'))
        write(new, {'api.h': API_H, 'src/collector.c': ren(GC_C), 'src/front.c': ren(HOST_C)})
        r = similarity.compare(self.legacy, new, ['api.h'])
        self.assertEqual(r['M2_name_reuse'], 0.0)            # all internal names changed ...
        self.assertGreaterEqual(r['M4_function_mirror'], 0.99)  # ... but the functions are the same
        self.assertGreaterEqual(r['M3_clone_ratio'], 0.9)
        self.assertGreaterEqual(r['M1_file_mirror'], 0.99)   # module boundaries preserved (content-based)
        self.assertLess(r['verbatim_ratio'], r['M3_clone_ratio'])

    def test_independent_design_is_low(self):
        new = os.path.join(self.tmp, 'new')
        write(new, {'api.h': API_H, 'core/pool.c': POOL_C})
        r = similarity.compare(self.legacy, new, ['api.h'])
        self.assertLess(r['LSS'], 15)
        self.assertEqual(r['M4_function_mirror'], 0.0)

    def test_contract_names_not_counted(self):
        new = os.path.join(self.tmp, 'new')
        write(new, {'api.h': API_H, 'core/pool.c': POOL_C})
        r = similarity.compare(self.legacy, new, ['api.h'], detail=True)
        self.assertNotIn('fwsubmit', r['detail']['reused_names'])

    def test_java_methods(self):
        j = os.path.join(self.tmp, 'j')
        write(j, {'src/main/java/a/Proc.java': '''package a;
public class Proc implements Runnable {
    private final java.util.List<String> xs = new java.util.ArrayList<>();
    @Override public void run() { for (String x : xs) { if (x.isEmpty()) continue; System.out.println(x.trim()); } }
    public int score(String s) throws Exception { Runnable r = () -> { }; return new Object() { int f() { return 1; } }.f() + s.length(); }
}'''})
        f = similarity.SourceFile(j, 'src/main/java/a/Proc.java')
        names = [n for n, _ in f.functions]
        self.assertEqual(names, ['run', 'score'])
        self.assertIn('Proc', f.types)


    def _funcs(self, name, text):
        d = os.path.join(self.tmp, 'f')
        write(d, {name: text})
        return [n for n, _ in similarity.SourceFile(d, name).functions]

    def test_annotated_java_class_and_record_keep_their_methods(self):
        self.assertEqual(self._funcs('C.java', '@RequestMapping("/api")\n@Table(name = "T")\npublic class Ctl extends B '
                                     'implements I {\n int a(int x){ return x+1; }\n int b(){ return 2; }\n}\n'), ['a', 'b'])
        self.assertEqual(self._funcs('R.java', 'public record Foo(int x) {\n int twice(){ return x*2; }\n}\n'), ['twice'])

    def test_trailing_return_types(self):
        self.assertEqual(self._funcs('a.ts', 'export function foo(a: number): Promise<number> { return a; }\n'
                                     'const f = (a) => { return a; };\n'), ['foo'])
        self.assertEqual(self._funcs('a.kt', 'class K(val x: Int) {\n fun foo(a: Int): Int { return a }\n}\n'), ['foo'])
        self.assertEqual(self._funcs('a.rs', 'fn foo(a: i32) -> i32 { a + 1 }\n'), ['foo'])
        self.assertEqual(self._funcs('a.go', 'func f(a int) (int, error) { return a, nil }\n'), ['f'])
        self.assertEqual(self._funcs('a.c', 'int f(int a) { if (a) { return 1; } return 0; }\n'
                                     'static const int t[] = { 1, 2 };\n'), ['f'])

    def test_python_multiline_signature_keeps_body(self):
        d = os.path.join(self.tmp, 'p')
        write(d, {'a.py': 'def foo(\n    a,\n    b,\n):\n    x = a + b\n    y = x * 2\n    return x * y\n'})
        (name, body), = similarity.SourceFile(d, 'a.py').functions
        self.assertEqual(name, 'foo')
        self.assertIn('return', body)

    def test_missing_or_empty_tree_is_an_error_not_a_pass(self):
        with self.assertRaises(ValueError):
            similarity.compare(os.path.join(self.tmp, 'nope'), self.legacy)
        empty = os.path.join(self.tmp, 'empty')
        write(empty, {'build/x.c': 'int f(void){return 0;}', 'README.md': 'x'})
        with self.assertRaises(ValueError):
            similarity.compare(self.legacy, empty)

    def test_contract_glob_matches_at_other_depth(self):
        new = os.path.join(self.tmp, 'new')
        write(new, {'api/api.h': API_H, 'core/pool.c': POOL_C})
        r = similarity.compare(self.legacy, new, ['include/api.h'])
        self.assertEqual(r['legacy']['contract_files'], ['api.h'])
        self.assertEqual(r['new']['contract_files'], ['api/api.h'])
        self.assertFalse(similarity.is_contract('src/hal_x.h', ['hal/*.h']))
        self.assertTrue(similarity.is_contract('src/hal/x.h', ['hal/*.h']))

    def test_kit_tool_contract_list_is_fixed_even_when_empty(self):
        import contextlib, io, shutil as sh
        kit = os.path.join(self.tmp, 'kit')
        os.makedirs(os.path.join(kit, 'tools'))
        sh.copy(similarity.__file__, os.path.join(kit, 'tools', 'structure_check.py'))
        sys.path.insert(0, os.path.join(kit, 'tools'))
        try:
            import structure_check
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                structure_check.main([self.legacy, self.legacy, '--contract', '*'])
        finally:
            sys.path.pop(0)
        text = out.getvalue()
        self.assertIn('LSS (레거시 구조 유사도) 100.0', text)     # '*' did not become the official contract list
        self.assertIn('판정: 미달', text)
        self.assertIn('참고용', text)


if __name__ == '__main__':
    unittest.main()
