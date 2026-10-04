import copy,json,unittest
from experiments.context_policy.reader_decision_protocol import parse_decision,render_decision,decision_messages
class DecisionProtocol(unittest.TestCase):
 def setUp(self):
  self.history=[{'role':'user','content':'My supplied code is AL-2.'},{'role':'assistant','content':'Your code is AL-3.'}]
  self.query='Is AL-3 the code I supplied?'
  self.record={'scope':'current','relation':'fact','status':'value','value':'AL-2','operation':'match','candidate':'AL-3','decision':'contradicted','turn':0,'quote':'My supplied code is AL-2.'}
 def parse(self,r):return parse_decision(json.dumps(r),self.history,self.query)
 def test_render_comparison_and_question_span(self):
  r=self.parse(self.record);self.assertTrue(r['valid']);self.assertEqual(render_decision(r),'No. The value you supplied is AL-2.')
  r=copy.deepcopy(self.record);r['candidate']='AL-9';self.assertFalse(self.parse(r)['valid'])
 def test_unknown_does_not_repeat_withdrawn_values(self):
  h=self.history+[{'role':'user','content':'Forget my supplied code.'}]
  r={**self.record,'status':'unknown','value':None,'decision':'unknown','turn':2,'quote':'Forget my supplied code.'}
  p=parse_decision(json.dumps(r),h,self.query);self.assertTrue(p['valid']);self.assertEqual(render_decision(p),'The current detail is unknown.')
 def test_no_semantic_repair(self):
  r={**self.record,'decision':'supported'};p=self.parse(r)
  self.assertTrue(p['valid']);self.assertTrue(render_decision(p).startswith('Yes.')) # semantic review must fail this
 def test_invalid_is_not_credited_as_unknown(self):
  r={**self.record,'turn':1,'quote':'Your code is AL-3.','value':'AL-3'}
  p=self.parse(r);self.assertFalse(p['valid']);self.assertNotIn('unknown',render_decision(p))
  text=json.dumps(self.record).replace('"scope": "current"','"scope": "current", "scope": "current"')
  self.assertFalse(parse_decision(text,self.history,self.query)['valid'])
 def test_none_is_distinct_from_negative(self):
  h=[{'role':'user','content':'I do not prefer satin. No alternative is selected.'}]
  q='Do I prefer satin?';r={**self.record,'relation':'preference','status':'negative','value':'satin','candidate':'satin','quote':h[0]['content']}
  p=parse_decision(json.dumps(r),h,q);self.assertTrue(p['valid']);self.assertIn('do not prefer satin',render_decision(p))
  # Quoted text alone cannot certify the typed status.
  r.update(status='none',value=None);p=parse_decision(json.dumps(r),h,q);self.assertTrue(p['valid']);self.assertIn('no preference',render_decision(p))
 def test_other_activity_is_not_automatically_denied(self):
  h=[{'role':'user','content':'I enjoy pottery.'}];q='Do I enjoy juggling?'
  r={**self.record,'relation':'enjoyment','status':'value','value':'pottery','candidate':'juggling','decision':'unknown','quote':'I enjoy pottery.'}
  p=parse_decision(json.dumps(r),h,q);self.assertTrue(p['valid']);self.assertEqual(render_decision(p),'Whether you enjoy the queried activity is unknown. You enjoy pottery.')
 def test_prompts_have_only_archive_question(self):
  messages=decision_messages(self.history,self.query)
  self.assertEqual(len(messages),2);self.assertIn(self.query,messages[1]['content']);self.assertNotIn('TARGET PROPERTY',messages[1]['content'])
if __name__=='__main__':unittest.main()
