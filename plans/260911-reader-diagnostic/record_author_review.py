"""Record author decisions after reading all 96 frozen captures; no inference."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
P=Path(__file__).resolve().parent
if (P/'result-manifest.json').exists():
 raise SystemExit('Results are frozen; preserve the recorded author review.')
captures=json.loads((P/'run/captures.json').read_text());cases={c['id']:c for c in json.loads((P/'preflight/cases.json').read_text())}
# These indices are explicit author judgments from the saved outputs, not a keyword classifier.
stale={0,1,2,3,24,25,26,27}
ignored_later={17,18,40,41,64,67,89,90}
withdrawal_negative={20,21,22,23,44,45,46,47}
wrong_owner={61,62}
old_value_repeated={4,5,28,29,79,68,69,71,92,93,94,95}
assert len(stale|ignored_later|withdrawal_negative|wrong_owner)==26
assert not old_value_repeated & (stale|ignored_later|withdrawal_negative|wrong_owner)
answers=[]
for i,c in enumerate(captures):
 assert c['input_index']==i
 case=cases[c['id']]
 fields=dict.fromkeys(('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct'),True)
 notes=[]
 if i in stale:
  for k in ('task_complete','source_consistent','supported_in_visible_state'):fields[k]=False
  notes.append('The latest direct user assertion establishes the positive activity preference, with no withdrawal, intervening change or elapsed-time premise. The answer invents a requirement for another current confirmation and abstains; under the frozen baseline reference it is incomplete and its staleness explanation is unsupported.')
 if i in ignored_later:
  for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant'):fields[k]=False
  notes.append('The later explicit user statement at T4 re-establishes the same value after the T2 withdrawal. The answer reports a negative or unknown value and gives priority to the earlier withdrawal despite preserved turn numbers. Both the requested value and explanation are wrong.')
 if i in withdrawal_negative:
  for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant'):fields[k]=False
  notes.append('A definite No to the current enjoyment question turns withdrawal into a negative preference. No later negative is present. The current value is unknown, not a known dislike or absence of enjoyment.')
 if i in wrong_owner:
  for k in ('task_complete','source_consistent','supported_in_visible_state','ownership_correct'):fields[k]=False
  notes.append('The pears preference is explicitly a fictional first-person line spoken by Rowan. The answer states it as the current user preference even though the source and question do not establish that ownership.')
 if i in old_value_repeated:
  fields['withdrawal_compliant']=False
  notes.append('The final value or unknown status is correct, but the current-value answer repeats the specifically withdrawn old preference while explaining withdrawal. The frozen system forbids this restatement. Source truth and visible support remain true: the old statement is present, but repeating it violates the output rule. Mentioning only the topic would not fail.')
 if not notes:
  if case['kind']=='historical':notes.append('Correctly reports the original user statement at the question\'s historical textual scope. First-person echoes inherit that scope; referring to the user\'s second message denotes T2, not the intervening assistant turn.')
  elif case['kind']=='ownership':notes.append('Correctly distinguishes the fictional Rowan statement from user biography and says the current user preference is unknown.')
  elif case['kind']=='withdrawal':notes.append('Correctly says the current value is unknown without asserting its opposite or repeating the old named value.')
  else:notes.append('Correctly gives the latest valid direct user preference. Any explanation respects the applicable withdrawal and later update; missing an explicit citation is not penalized.')
 evidence=[{'where':'answer','index':0,'quote':c['text']}]
 for turn in case['reference']['evidence_turns']:
  text=case['history'][turn]['content'];evidence.append({'where':'history','index':turn,'quote':text})
  candidates=(text,json.dumps(text,ensure_ascii=False)[1:-1])
  found=False
  for index,message in enumerate(c['messages']):
   for q in candidates:
    if q in message['content']:
     evidence.append({'where':'reader_message','index':index,'quote':q});found=True;break
   if found:break
  assert found,(i,turn)
 fields.update(body_valid=c['body_structurally_valid'],within_90_words=c['within_90_words'])
 answers.append({'id':c['id'],'arm':c['arm'],**fields,'verdict':'pass' if all(fields.values()) else 'fail','reason':' '.join(notes),'evidence':evidence})
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
review={'reviewer':'Codex, experiment author','model_version':'GPT-6','reviewed_at':datetime.now(timezone.utc).isoformat(),'status':'complete',
 'process_notes':'Author read all 96 frozen answers, grouped by case and condition, against the complete short sources and actual messages. This is unblinded author model review, not independent validation. The explicit decision-index sets encode these inspected judgments, not inferred ground truth from keyword matching. All sources were visible. Literal statements of an old positive activity preference count as withdrawn-value repetition; topic-only references do not. Forget wording is interpreted as requested record status, not evidence of physical erasure. No hidden reasoning is inferred merely from a correct uncited answer. First-person echoes retain the user or historical passage referent when clear.',
 'captures_sha256':sha(P/'run/captures.json'),'cases_sha256':sha(P/'preflight/cases.json'),'answers':answers,'training_labels':0}
(P/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print('Saved 96 explicit author judgments')
