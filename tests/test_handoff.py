"""Exercise the real CLI in isolated sessions; no host conversation access."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]

class Handoff(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'session';self.root.mkdir()
        self.user=self.root/'user.txt';self.user.write_text('继续完成研究任务。'*10,encoding='utf-8')
        self.assistant=self.root/'assistant.txt';self.assistant.write_text('已完成一个阶段。',encoding='utf-8')
        self.approval=self.root/'approval.txt';self.approval.write_text('好的，请帮我压缩',encoding='utf-8')
        self.memory=self.root/'project-memory.md';self.memory.write_text('读者：硕士生\n目标：保持引用准确',encoding='utf-8')
        self.notes=self.root/'compression-notes.md';self.notes.write_text('压缩范围：本次显式登记的原文。',encoding='utf-8')
    def runcli(self,script,*args,ok=True):
        result=subprocess.run([sys.executable,'-X','utf8',str(BASE/'scripts'/script),'--root',str(self.root),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode==0,ok,result.stderr+result.stdout)
        return json.loads(result.stdout) if result.returncode==0 else result.stderr
    def meter(self,*args,**kw):return self.runcli('session_meter.py',*args,**kw)
    def guard(self,*args,**kw):return self.runcli('memory_guard.py',*args,**kw)
    def init(self):return self.meter('init','--every',2,'--threshold',10)
    def turn(self,key,kind='task'):return self.meter('record-turn','--user-file',self.user,'--assistant-file',self.assistant,'--key',key,'--kind',kind)
    def publish(self,basis='archive-approval'):return self.guard('publish','--files','project-memory.md','compression-notes.md','--instruction',self.approval,'--basis',basis)
    def test_cadence_over_threshold_does_not_trigger_early(self):
        self.init();a=self.turn('a');self.assertFalse(a['checkpoint_due']);self.meter('checkpoint',ok=False)
        b=self.turn('b');self.assertTrue(b['checkpoint_due']);c=self.meter('checkpoint');self.assertTrue(c['checkpoint_report']['archive_suggested'])
        self.assertFalse(c['checkpoint_due'])
    def test_control_turn_does_not_advance(self):
        self.init();self.turn('control','control');self.assertEqual(self.meter('status')['completed_rounds'],0)
    def test_duplicate_id_idempotent(self):
        self.init();self.turn('one');self.turn('one');self.assertEqual(self.meter('status')['completed_rounds'],1)
    def test_duplicate_changed_content_rejected(self):
        self.init();self.turn('one');self.user.write_text('changed',encoding='utf-8');self.runcli('session_meter.py','record-turn','--user-file',self.user,'--assistant-file',self.assistant,'--key','one',ok=False)
    def test_archive_requires_approval(self):
        self.init();self.turn('one');self.meter('archive','--memory',self.memory,'--explanation',self.notes,ok=False)
    def test_approval_does_not_cover_new_tail(self):
        self.init();self.turn('one');self.meter('approve','--file',self.approval);self.turn('two')
        result=self.meter('archive','--memory',self.memory,'--explanation',self.notes);self.assertEqual(result['unarchived_events'],2)
        self.assertEqual(len(list((self.root/'raw').iterdir())),5)
    def test_tampered_raw_blocks_archive(self):
        self.init();self.turn('one');self.meter('approve','--file',self.approval);(self.root/'raw/00001.txt').write_text('changed',encoding='utf-8')
        self.meter('archive','--memory',self.memory,'--explanation',self.notes,ok=False)
    def test_inspect_read_only(self):
        self.publish();before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()};self.guard('inspect')
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_working_divergence_reported(self):
        self.publish();self.memory.write_text('changed',encoding='utf-8');result=self.guard('inspect');self.assertFalse(result['files'][0]['working_copy_matches'])
    def test_correction_and_restore_preserve_working_copy(self):
        original=self.memory.read_bytes();self.publish();self.memory.write_text('读者：博士生',encoding='utf-8');self.publish('user-correction')
        self.memory.write_text('尚未发布的新内容',encoding='utf-8');result=self.guard('restore','--revision',1,'--instruction',self.approval)
        self.assertEqual(result['revision'],3);self.assertEqual(self.memory.read_bytes(),original)
        self.assertIn('尚未发布',(self.root/'protected-memory/revision-00003/working-before-001.txt').read_text(encoding='utf-8'))
    def test_protected_tamper_detected(self):
        self.publish();(self.root/'protected-memory/revision-00001/001.txt').write_text('bad',encoding='utf-8');self.guard('inspect',ok=False)
    def test_outside_path_rejected(self):
        outside=Path(self.tmp.name)/'outside.md';outside.write_text('private',encoding='utf-8');self.guard('publish','--files','../outside.md','--instruction',self.approval,'--basis','archive-approval',ok=False)

if __name__=='__main__':unittest.main()
