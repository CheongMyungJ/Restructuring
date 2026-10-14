"""Headless Claude Code runner (claude -p) with transcript logging, cost accounting and retries."""
import json, os, subprocess, time

class ClaudeError(RuntimeError):
    pass


# Each engine step is meant to be one self-contained session. Sub-agents and background/scheduled work made
# cost unpredictable (a synthesis session that spawned 5 sub-agents cost 3.5x its sibling run), so they are off.
DISALLOWED_TOOLS = ['Agent', 'Task', 'Monitor', 'ScheduleWakeup', 'CronCreate', 'RemoteTrigger', 'Workflow']


def claude_available():
    try:
        return subprocess.run(['claude', '--version'], capture_output=True, text=True, timeout=30).returncode == 0
    except Exception:
        return False


def run_claude(prompt, cwd, log_path, model=None, effort=None, add_dirs=(), timeout_s=3 * 3600,
               json_schema=None, max_retries=2, extra_args=(), allowed_tools=None):
    """Run one headless session. Returns dict(result, cost_usd, wall_s, num_turns, session_id, is_error, structured)."""
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    cmd = ['claude', '-p', '--output-format', 'stream-json', '--verbose', '--permission-mode', 'bypassPermissions',
           '--no-session-persistence']
    if model:
        cmd += ['--model', model]
    if effort:
        cmd += ['--effort', effort]
    for d in add_dirs:
        cmd += ['--add-dir', d]
    if json_schema:
        cmd += ['--json-schema', json.dumps(json_schema)]
    if allowed_tools:
        cmd += ['--tools', ','.join(allowed_tools)]
    else:
        cmd += ['--disallowedTools', ','.join(DISALLOWED_TOOLS)]
    cmd += list(extra_args)
    attempt = 0
    while True:
        attempt += 1
        t0 = time.time()
        result, timed_out = None, False
        with open(log_path if attempt == 1 else f'{log_path}.retry{attempt}', 'w', encoding='utf-8') as log:
            proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            proc.stdin.write(prompt)
            proc.stdin.close()
            for line in proc.stdout:
                log.write(line)
                log.flush()
                if '"type":"result"' in line or '"type": "result"' in line:
                    try:
                        ev = json.loads(line)
                        if ev.get('type') == 'result':
                            result = ev
                    except Exception:
                        pass
                if time.time() - t0 > timeout_s:
                    timed_out = True
                    proc.kill()
                    break
            proc.wait()
        out = {
            'result': (result or {}).get('result', ''),
            'structured': (result or {}).get('structured_output'),
            'cost_usd': (result or {}).get('total_cost_usd') or 0.0,
            'wall_s': round(time.time() - t0, 1),
            'num_turns': (result or {}).get('num_turns'),
            'session_id': (result or {}).get('session_id'),
            'is_error': bool((result or {}).get('is_error', True)) or timed_out,
            'timed_out': timed_out,
            'log': log_path,
        }
        low = (out['result'] or '').lower()
        if out['is_error'] and ((result or {}).get('api_error') == 'usage_limit_reached' or 'limit' in low and ('session' in low or 'usage' in low)):
            out['usage_limit'] = True
            return out                    # not transient on a 30s scale: let the pipeline stop (resumable)
        transient = (result is None and not timed_out) or (
            out['is_error'] and any(s in (out['result'] or '').lower() for s in ('overloaded', 'rate limit', '529', 'timeout', 'api error')))
        if transient and attempt <= max_retries:
            time.sleep(30 * attempt)
            continue
        return out
