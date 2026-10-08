"""Prove an unexercised branch or unimported module cannot pass the Python gate."""
import os
import subprocess
import sys
from pathlib import Path
import json


def test_python_gate_rejects_uncovered_branch_and_unimported_module(tmp_path):
    (tmp_path/'probe.py').write_text('def branch(value):\n    if value:\n        return 1\n    return 0\n')
    (tmp_path/'unimported.py').write_text('def unused():\n    return 2\n')
    (tmp_path/'run.py').write_text('import probe\nassert probe.branch(True) == 1\n')
    env=dict(os.environ,COVERAGE_FILE=str(tmp_path/'.coverage'))
    measured=subprocess.run([sys.executable,'-m','coverage','run','--branch','--source',str(tmp_path),str(tmp_path/'run.py')],env=env,capture_output=True)
    assert measured.returncode==0
    result=subprocess.run([sys.executable,'-m','coverage','report','--fail-under=100'],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode==2 and 'unimported.py' in result.stdout and 'Coverage failure' in result.stdout


def test_javascript_gate_rejects_uncovered_branch_and_unimported_module(tmp_path):
    root=Path(__file__).resolve().parents[1]
    (tmp_path/'probe.js').write_text('export function branch(value) { if(value) return 1; return 0; }\n')
    (tmp_path/'unimported.js').write_text('export function unused() { return 2; }\n')
    (tmp_path/'probe.test.js').write_text("import {it, expect} from 'vitest';\nimport {branch} from './probe.js';\nit('one branch',()=>expect(branch(true)).toBe(1));\n")
    # Resolve the test dependency from the project's installed tree, while the
    # generated probe and its deliberately failing report remain private.
    vitest=(root/'node_modules/vitest/dist/index.js').as_uri()
    (tmp_path/'probe.test.js').write_text((tmp_path/'probe.test.js').read_text().replace("'vitest'",json.dumps(vitest)))
    config=tmp_path/'vitest.config.mjs'
    config.write_text('import base from '+json.dumps((root/'vitest.config.js').as_uri())+';\nexport default {...base, root:'+json.dumps(tmp_path.as_posix())+",test:{...base.test,include:['probe.test.js'],environment:'node',coverage:{...base.test.coverage,include:['probe.js','unimported.js'],reporter:['text']}}};\n")
    result=subprocess.run(['node',str(root/'node_modules/vitest/vitest.mjs'),'run','--coverage','--config',str(config)],cwd=root,capture_output=True,text=True)
    assert result.returncode==1
    assert 'unimported.js' in result.stdout and 'branches' in result.stderr
