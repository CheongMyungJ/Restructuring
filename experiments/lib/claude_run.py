#!/usr/bin/env python3
"""Run `claude -p` headlessly with full transcript logging, cost/time accounting and path-access auditing.

Used by the experiments to (a) generate redevelopment data with different methods and
(b) let a fresh agent redevelop a system from that data in an isolated working directory.
"""
import json, os, re, subprocess, sys, time

DEFAULT_TOOLS_TIMEOUT = 4 * 3600


def run_claude(prompt, cwd, log_path, model=None, effort=None, timeout_s=DEFAULT_TOOLS_TIMEOUT,
               extra_args=None, forbidden_roots=(), resume=None, env_extra=None, json_schema=None,
               watch_roots=(), allowed_roots=()):
    """Run one headless Claude Code session. Returns a summary dict (also written next to the log)."""
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    cmd = ['claude', '-p', '--output-format', 'stream-json', '--verbose',
           '--permission-mode', 'bypassPermissions']
    if model:
        cmd += ['--model', model]
    if effort:
        cmd += ['--effort', effort]
    if resume:
        cmd += ['--resume', resume]
    if json_schema:
        cmd += ['--json-schema', json.dumps(json_schema)]
    cmd += list(extra_args or [])
    env = dict(os.environ)
    env.update(env_extra or {})
    t0 = time.time()
    result = None
    with open(log_path, 'w', encoding='utf-8') as log:
        proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, env=env, bufsize=1)
        proc.stdin.write(prompt)
        proc.stdin.close()
        deadline = t0 + timeout_s
        timed_out = False
        for line in proc.stdout:
            log.write(line)
            log.flush()
            if line.startswith('{') and '"type":"result"' in line.replace(' ', ''):
                try:
                    result = json.loads(line)
                except Exception:
                    pass
            if time.time() > deadline:
                timed_out = True
                proc.kill()
                break
        proc.wait()
    summary = {
        'cwd': cwd, 'log': log_path, 'model': model, 'exit_code': proc.returncode,
        'timed_out': timed_out, 'wall_s': round(time.time() - t0, 1),
        'cost_usd': (result or {}).get('total_cost_usd'),
        'num_turns': (result or {}).get('num_turns'),
        'session_id': (result or {}).get('session_id'),
        'is_error': (result or {}).get('is_error', True),
        'result': (result or {}).get('result', '')[-4000:],
        'usage': (result or {}).get('usage'),
        'model_usage': (result or {}).get('modelUsage'),
    }
    summary['audit'] = audit_log(log_path, forbidden_roots, watch_roots, allowed_roots or (cwd,))
    with open(log_path + '.summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    return summary


PATH_RE = re.compile(r'(/[A-Za-z0-9._\-/+@가-힣]+)')


def _under(p, root):
    return p == root or p.startswith(root.rstrip(os.sep) + os.sep)


def audit_log(log_path, forbidden_roots=(), watch_roots=(), allowed_roots=()):
    """Find tool calls that touched forbidden paths (leak detection) and count tool usage.
    A path is a violation if it is under a forbidden root, or under a watch root but not under an allowed root."""
    hits, tool_counts = [], {}
    forbidden_roots = [os.path.realpath(r) for r in forbidden_roots]
    watch_roots = [os.path.realpath(r) for r in watch_roots]
    allowed_roots = [os.path.realpath(r) for r in allowed_roots]
    try:
        lines = open(log_path, encoding='utf-8').read().splitlines()
    except FileNotFoundError:
        return {'violations': [], 'tool_counts': {}}
    for line in lines:
        if not line.startswith('{'):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get('type') != 'assistant':
            continue
        for block in (ev.get('message') or {}).get('content') or []:
            if block.get('type') != 'tool_use':
                continue
            name = block.get('name')
            tool_counts[name] = tool_counts.get(name, 0) + 1
            blob = json.dumps(block.get('input', {}), ensure_ascii=False)
            for p in PATH_RE.findall(blob):
                rp = os.path.realpath(p)
                bad = any(_under(rp, r) for r in forbidden_roots)
                if not bad and any(_under(rp, r) for r in watch_roots):
                    bad = not any(_under(rp, r) for r in allowed_roots)
                if bad:
                    hits.append({'tool': name, 'path': p, 'input': blob[:300]})
    return {'violations': hits[:50], 'violation_count': len(hits), 'tool_counts': tool_counts}


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--cwd', required=True)
    ap.add_argument('--prompt-file', required=True)
    ap.add_argument('--log', required=True)
    ap.add_argument('--model')
    ap.add_argument('--effort')
    ap.add_argument('--timeout', type=int, default=DEFAULT_TOOLS_TIMEOUT)
    ap.add_argument('--forbid', action='append', default=[])
    a = ap.parse_args()
    s = run_claude(open(a.prompt_file, encoding='utf-8').read(), a.cwd, a.log, model=a.model,
                   effort=a.effort, timeout_s=a.timeout, forbidden_roots=a.forbid)
    print(json.dumps({k: s[k] for k in ('exit_code', 'timed_out', 'wall_s', 'cost_usd', 'num_turns', 'is_error')}))
    print('audit violations:', s['audit'].get('violation_count'))
