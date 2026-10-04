import unittest,json
from experiments.context_policy.reader_factor_protocol import parse_record,project,record_messages
class FactorTest(unittest.TestCase):
 def test_projection_distinguishes_none_unknown_negative(self):
  q={'operation':'matches_value','candidate':'A'}
  self.assertEqual(project({'status':'none','value':None},q),{'kind':'boolean','value':False})
  self.assertEqual(project({'status':'unknown','value':None},q),{'kind':'unknown','value':None})
  self.assertEqual(project({'status':'negative','value':'B'},q),{'kind':'unknown','value':None})
  self.assertEqual(project({'status':'negative','value':'A'},q),{'kind':'boolean','value':False})
 def test_exact_matching_no_fuzzy_alias(self):
  r={'status':'value','value':'Ravn'}
  self.assertFalse(project(r,{'operation':'matches_value','candidate':'Raven'})['value'])
  self.assertTrue(project(r,{'operation':'matches_value','candidate':'Ravn'})['value'])
 def test_reject_assistant_quote_and_bad_schema(self):
  h=[{'role':'user','content':'My code is L8R.'},{'role':'assistant','content':'LBR'}]
  good={'status':'value','value':'L8R','turn':0,'quote':'My code is L8R.'}
  self.assertTrue(parse_record(json.dumps(good),h)['valid'])
  for r in ({**good,'turn':1},{**good,'value':'LBR'},{**good,'extra':1},{**good,'turn':True}):
   self.assertFalse(parse_record(json.dumps(r),h)['valid'])
 def test_quotes_are_not_semantic_certificates(self):
  h=[{'role':'user','content':'Fictional Li said: My code is L8R.'}]
  r={'status':'value','value':'L8R','turn':0,'quote':h[0]['content']}
  self.assertTrue(parse_record(json.dumps(r),h)['valid']) # source anchoring alone cannot validate ownership
 def test_canonical_messages(self):
  a={'status':'value','value':'A','turn':0,'quote':'A'};b=dict(reversed(list(a.items())))
  self.assertEqual(record_messages('code',a,'Which?'),record_messages('code',b,'Which?'))
if __name__=='__main__':unittest.main()
