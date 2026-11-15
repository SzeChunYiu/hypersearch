import concurrent.futures
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from hypersearch import review_workflow as flow
from hypersearch.study_json import encode
from review_fixture import report
from study_fixture import git, launch
import unittest
import test_review_workflow as common


class ReviewBoundaryTests(unittest.TestCase):
    setUp = common.ReviewWorkflowTests.setUp
    start = common.ReviewWorkflowTests.start
    snapshot = common.ReviewWorkflowTests.snapshot

    def test_actual_cli_handoff_after_grant(self):
        bundle = self.root/"bundle.json"; bundle.write_bytes(encode(self.value))
        env = dict(os.environ, PYTHONPATH=str(self.core/"src"), PYTHONDONTWRITEBYTECODE="1")
        common = ["--bundle", str(bundle), "--consumer-root", str(self.consumer),
                  "--db", str(self.kw["database"]), "--export", str(self.kw["export"])]
        def run(action, *extra):
            result = subprocess.run([sys.executable,*launch(self.root/"private-cache"),"-m","hypersearch",action,*common,*extra],
                                    env=env,cwd=self.root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        run("register-review"); token = run("grant-review")
        self.assertEqual(self.snapshot()["budget"]["spent"],1)
        # This synthetic author produces output only after the persisted grant.
        grantfile=self.root/"grant.json"; grantfile.write_bytes(encode(token))
        reportfile=self.root/"report.json"; reportfile.write_bytes(encode(report(self.value,token)))
        result=run("submit-review","--grant",str(grantfile),"--report",str(reportfile))
        self.assertEqual(run("recover-review")["receipt_sha256"],result["receipt_sha256"])
        self.assertEqual(self.snapshot()["budget"]["spent"],1)

    def test_two_final_submissions_only_one_wins(self):
        token=self.start(); authored=report(self.value,token)
        def submit():
            try:
                flow.submit(self.value,token,authored,**self.kw)
                return True
            except ValueError:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda _: submit(),range(2)))
        self.assertEqual(sorted(results),[False,True])
        self.assertEqual(len(self.snapshot()["results"]),1)
        self.assertEqual(self.snapshot()["budget"]["spent"],1)

    def test_hidden_source_mutation_refused(self):
        path=self.core/"src/hypersearch/store.py"
        git(self.core,"update-index","--assume-unchanged","src/hypersearch/store.py")
        path.write_bytes(path.read_bytes()+b"\n# changed\n")
        with self.assertRaisesRegex(ValueError,"working bytes"):
            flow.register(self.value,**self.kw)
        self.assertFalse(self.kw["database"].exists())

    def test_ignored_executable_source_refused(self):
        (self.core/".git/info/exclude").write_text("src/hypersearch/unknown.py\n")
        (self.core/"src/hypersearch/unknown.py").write_text("# inert fixture\n")
        with self.assertRaisesRegex(ValueError,"untracked executable"):
            flow.register(self.value,**self.kw)
        self.assertFalse(self.kw["database"].exists())

    def test_sidecar_input_and_hardlink_database_refused(self):
        sidecar=Path(str(self.kw["database"])+"-journal");sidecar.write_bytes(b"input")
        with self.assertRaises(ValueError): flow.register(self.value,inputs=(sidecar,),**self.kw)
        self.assertEqual(sidecar.read_bytes(),b"input"); sidecar.unlink()
        flow.register(self.value,**self.kw)
        link=self.root/"db-hardlink";os.link(self.kw["database"],link)
        before=link.read_bytes()
        with self.assertRaisesRegex(ValueError,"hardlinked"):
            flow.grant(self.value,**self.kw)
        self.assertEqual(link.read_bytes(),before)

    def test_grant_and_recover_missing_database_do_not_create(self):
        for action in (flow.grant,flow.recover):
            with self.assertRaises(Exception): action(self.value,**self.kw)
            self.assertFalse(self.kw["database"].exists())

    def test_role_lineage_conflict(self):
        value=copy.deepcopy(self.value);value["exclusions"].append("orchestrator-b")
        with self.assertRaisesRegex(ValueError,"role conflict"): flow.register(value,**self.kw)
        self.assertFalse(self.kw["database"].exists())
