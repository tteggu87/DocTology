"""Citation matching tests use independent source files and native transcript-shaped inputs."""
import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('native_citations_test',Path(__file__).resolve().parents[1]/'runtime/wiki_dashboard_native_citations.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class NativeCitationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'wiki').mkdir()
        self.text='# Source A\n\nA unique evidence sentence 7319.\n'
        (self.root/'wiki/a.md').write_text(self.text)
        (self.root/'wiki/b.md').write_text('# Source B\n\nAnother evidence sentence.\n')
        self.collector=module.NativeCitations(self.root)
    def read(self,path='wiki/a.md',text=None,prefix='1',parent=None,error=False):
        return [
            {'id':'c'+prefix,'parentId':parent,'type':'message','message':{'role':'assistant','content':[{'type':'toolCall','name':'read','id':'t'+prefix,'arguments':{'path':path}}]}},
            {'id':'r'+prefix,'parentId':'c'+prefix,'type':'message','message':{'role':'toolResult','toolName':'read','toolCallId':'t'+prefix,'isError':error,'content':[{'type':'text','text':self.text if text is None else text}]}}
        ]
    def ingest(self,entries,leaf):self.collector.update({'entries':entries,'leafId':leaf})
    def test_successful_read_plus_explicit_link_connects_only_cited_document(self):
        self.ingest(self.read()+self.read('wiki/b.md',(self.root/'wiki/b.md').read_text(),'2','r1'),'r2')
        refs,reads=self.collector.project('A fact [Source A](wiki/a.md).')
        self.assertEqual([r['id'] for r in refs],['wiki/a.md'])
        self.assertEqual({r['id'] for r in reads},{'wiki/a.md','wiki/b.md'})
        self.assertEqual(refs[0]['contentHash'],hashlib.sha256(self.text.encode()).hexdigest())
    def test_followup_and_resume_use_native_history_not_browser_text(self):
        entries=self.read();self.ingest(entries,'r1')
        self.assertEqual(self.collector.request_arguments(),{'since':'r1'})
        self.ingest([{'id':'next','parentId':'r1','type':'message','message':{'role':'user','content':'followup'}}],'next')
        self.assertEqual(len(self.collector.project('[A](wiki/a.md)')[0]),1)
        resumed=module.NativeCitations(self.root);resumed.update({'entries':entries,'leafId':'r1'})
        self.assertEqual(len(resumed.project('[A](wiki/a.md)')[0]),1)
    def test_abandoned_branch_and_error_reads_do_not_become_citations(self):
        self.ingest(self.read()+self.read('wiki/b.md',(self.root/'wiki/b.md').read_text(),'2',None),'r2')
        self.assertEqual(self.collector.project('[A](wiki/a.md)')[0],[])
        self.collector=module.NativeCitations(self.root)
        self.ingest(self.read(error=True),'r1')
        self.assertEqual(self.collector.project('[A](wiki/a.md)')[0],[])
    def test_unread_changed_missing_and_outside_sources_are_not_connected(self):
        self.ingest(self.read(),'r1')
        self.assertEqual(self.collector.project('[B](wiki/b.md)')[0],[])
        (self.root/'wiki/a.md').write_text('# Changed\nNew content\n')
        self.assertEqual(self.collector.project('[A](wiki/a.md)')[0],[])
        (self.root/'wiki/a.md').unlink()
        self.assertEqual(self.collector.project('[A](wiki/a.md)')[0],[])
        self.collector=module.NativeCitations(self.root)
        self.ingest(self.read('../outside.md'),'r1')
        self.assertEqual(self.collector.project('[outside](../outside.md)')[1],[])
    def test_code_and_filename_mentions_do_not_count_but_valid_links_do(self):
        self.ingest(self.read(),'r1')
        for answer in ['wiki/a.md','`[A](wiki/a.md)`','```md\n[A](wiki/a.md)\n```','```\n[A](wiki/a.md)','[web](https://host/wiki/a.md)','![image](wiki/a.md)']:
            self.assertEqual(self.collector.project(answer)[0],[],answer)
        for answer in ['[A](./wiki/a.md#section)','[[wiki/a|A]]','[[a]]']:
            self.assertEqual(len(self.collector.project(answer)[0]),1,answer)
    def test_ambiguous_wikilinks_symlinks_and_broken_branch_fail_closed(self):
        (self.root/'wiki/other').mkdir();(self.root/'wiki/other/a.md').write_text(self.text)
        self.ingest(self.read(),'r1');self.assertEqual(self.collector.project('[[a]]')[0],[])
        (self.root/'wiki/link.md').symlink_to(self.root/'wiki/a.md')
        self.ingest(self.read('wiki/link.md',prefix='2',parent='r1'),'r2')
        self.assertEqual(self.collector.project('[link](wiki/link.md)')[0],[])
        self.ingest([], 'missing')
        with self.assertRaises(ValueError):self.collector.project('[A](wiki/a.md)')

if __name__=='__main__':unittest.main()
