"""Offline tests for rekit's deterministic parts (no AI calls). Run: python3 -m unittest discover -s tests"""
import json, os, shutil, subprocess, sys, tempfile, unittest

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ENGINE)
from rekit import inventory, materials  # noqa: E402
from rekit.questions import QuestionStore  # noqa: E402
from rekit.pipeline import Pipeline  # noqa: E402

RK = [sys.executable, os.path.join(ENGINE, 'rekit.py')]


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='rekit_test_')
        self.code = os.path.join(self.tmp, 'code')
        os.makedirs(os.path.join(self.code, 'src'))
        open(os.path.join(self.code, 'src', 'ftl.c'), 'w').write(
            '#include "ftl.h"\nstatic int victim(int a) { return a; }\nint gc_run(void)\n{\n  return victim(1);\n}\n')
        open(os.path.join(self.code, 'src', 'ftl.h'), 'w').write('int gc_run(void);\n')
        open(os.path.join(self.code, 'src', 'Job.java'), 'w').write(
            'public class LoadJob {\n  public void execute(String d) {\n  }\n}\n')
        open(os.path.join(self.code, 'mapper.xml'), 'w').write('<mapper><select id="selectDevices">SELECT 1</select></mapper>')
        open(os.path.join(self.code, 'Makefile'), 'w').write('all:\n\tcc src/ftl.c\n')
        open(os.path.join(self.code, 'legacy.txt'), 'wb').write('한글 주석'.encode('cp949'))
        open(os.path.join(self.code, 'blob.bin'), 'wb').write(b'\x00\x01\x02')
        self.mat = os.path.join(self.tmp, 'docs')
        os.makedirs(self.mat)
        open(os.path.join(self.mat, 'note.md'), 'w').write('# 설계\n내용')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_inventory(self):
        inv = inventory.scan([('code', self.code)])
        by = {f['path']: f for f in inv['files']}
        self.assertEqual(by['src/ftl.c']['lang'], 'c')
        self.assertIn('gc_run', by['src/ftl.c']['symbols'])
        self.assertIn('victim', by['src/ftl.c']['symbols'])
        self.assertIn('LoadJob', by['src/Job.java']['symbols'])
        self.assertIn('selectDevices', by['mapper.xml']['symbols'])
        self.assertEqual(by['blob.bin']['kind'], 'binary')
        self.assertEqual(by['legacy.txt']['encoding'], 'cp949')
        self.assertTrue(by['Makefile']['build_file'])

    def test_materials(self):
        idx = materials.convert_all([('materials', self.mat)], os.path.join(self.tmp, 'mt'))
        self.assertEqual(len(idx), 1)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, 'mt', idx[0]['text'])))
        try:
            import docx  # noqa: F401
            import openpyxl
        except ImportError:
            return
        import docx as d
        doc = d.Document(); doc.add_heading('제목', 1); doc.add_paragraph('본문'); t = doc.add_table(rows=2, cols=2)
        t.cell(0, 0).text = 'A'; t.cell(1, 1).text = 'B'
        doc.save(os.path.join(self.mat, 'spec.docx'))
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Layout'; ws.append(['offset', 'len']); ws.append([0, 16])
        wb.save(os.path.join(self.mat, 'if.xlsx'))
        idx = materials.convert_all([('materials', self.mat)], os.path.join(self.tmp, 'mt2'))
        texts = {e['source']: open(os.path.join(self.tmp, 'mt2', e['text']), encoding='utf-8').read() for e in idx if e.get('text')}
        self.assertIn('# 제목', texts['materials:spec.docx'])
        self.assertIn('| A |', texts['materials:spec.docx'])
        self.assertIn('Sheet: Layout', texts['materials:if.xlsx'])
        self.assertIn('| 0 | 16 |', texts['materials:if.xlsx'])

    def test_question_roundtrip(self):
        ws = os.path.join(self.tmp, 'ws')
        os.makedirs(os.path.join(ws, '.rekit', 'questions'))
        qf = os.path.join(ws, '.rekit', 'questions', 'x.json')
        json.dump([{'id': 'Q-A-01', 'priority': 'blocking', 'question': '운영 시간대는?', 'options': ['KST', 'UTC']},
                   {'id': 'Q-A-02', 'priority': 'minor', 'question': '사용 안 하는 잡?'}], open(qf, 'w'), ensure_ascii=False)
        s = QuestionStore(ws)
        self.assertEqual(s.ingest_file(qf, 'A'), 2)
        self.assertEqual(s.ingest_file(qf, 'A'), 0)          # idempotent
        self.assertEqual([q['id'] for q in s.pending()], ['Q-A-01', 'Q-A-02'])
        out = os.path.join(self.tmp, 'q.md')
        self.assertEqual(s.export_for_humans(out), 2)
        txt = open(out, encoding='utf-8').read()
        txt = txt.replace('답변:\n\n\n## Q-A-02', '답변: 1\n\n\n## Q-A-02', 1).rstrip() + ' 보류\n'
        txt = txt.replace('답변: 보류', '답변: 보류')
        open(out, 'w', encoding='utf-8').write(txt)
        self.assertEqual(s.import_from_humans(out), 2)
        s.save()
        by = QuestionStore(ws).by_id()
        self.assertEqual(by['Q-A-01']['status'], 'answered')
        self.assertEqual(by['Q-A-01']['answer'], 'KST')        # option number resolved
        self.assertEqual(by['Q-A-02']['status'], 'deferred')
        self.assertTrue(os.path.exists(os.path.join(ws, 'kit', '09_open_questions.md')))

    def test_cli_init_inventory_status(self):
        ws = os.path.join(self.tmp, 'work')
        r = subprocess.run(RK + ['init', ws, '--code', self.code, '--materials', self.mat, '--no-intake',
                                 '--intake-json', '{"goal": "플랫폼 교체"}'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('플랫폼 교체', open(os.path.join(ws, '.rekit', 'intake.md'), encoding='utf-8').read())
        r = subprocess.run(RK + ['run', ws, '--until', 'inventory'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(ws, '.rekit', 'inventory.json')))
        self.assertTrue(os.path.exists(os.path.join(ws, '.rekit', 'prompts', 'kitspec.md')))
        self.assertNotIn('{{LANG}}', open(os.path.join(ws, '.rekit', 'prompts', 'kitspec.md'), encoding='utf-8').read())
        r = subprocess.run(RK + ['status', ws, '--json'], capture_output=True, text=True)
        st = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(st['phases']['inventory'], 'done')
        self.assertEqual(st['run_state'], 'done')

    def test_coverage(self):
        ws = os.path.join(self.tmp, 'work2')
        subprocess.run(RK + ['init', ws, '--code', self.code, '--no-intake'], capture_output=True, text=True, check=True)
        subprocess.run(RK + ['run', ws, '--until', 'inventory'], capture_output=True, text=True, check=True)
        os.makedirs(os.path.join(ws, 'kit', '05_behavior'), exist_ok=True)
        open(os.path.join(ws, 'kit', '05_behavior', 'GC.md'), 'w').write('gc_run (src: src/ftl.c:3-6)')
        cov = Pipeline(ws).coverage()
        self.assertIn('code:src/ftl.c#victim', cov['unreferenced_symbols'])
        self.assertNotIn('code:src/ftl.c#gc_run', cov['unreferenced_symbols'])
        self.assertNotIn('code:src/ftl.c', cov['unreferenced_files'])

    def test_prompts_render(self):
        ws = os.path.join(self.tmp, 'work3')
        subprocess.run(RK + ['init', ws, '--code', self.code, '--no-intake'], capture_output=True, text=True, check=True)
        p = Pipeline(ws)
        for name, kw in (('survey.md', {'UNIT_TOKENS': 1}), ('unit_v2.md', {'UNIT_ID': 'GC', 'UNIT_TITLE': 't', 'FILES': '-', 'FOCUS': '', 'CHECKLIST': 'x'}),
                         ('synthesize_v2.md', {'SOURCES': 's'}), ('synthesize_group.md', {'GROUP_ID': 'G', 'GROUP_TITLE': 't', 'UNITS': 'GC'}),
                         ('characterize.md', {}), ('integrate.md', {}), ('review_v2.md', {'AREA': 'GC', 'AREA_ID': 'GC', 'FILES': 'f'}),
                         ('fix.md', {'BATCH': 'GC'}), ('finalize.md', {})):
            out = p.render(name, **kw)
            self.assertNotIn('{{', out, name)


if __name__ == '__main__':
    unittest.main()
