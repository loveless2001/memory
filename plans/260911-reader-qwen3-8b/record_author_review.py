"""Record explicit author decisions after inspection of all 144 saved answers."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
P=Path(__file__).resolve().parent
assert not (P/'result-manifest.json').exists(), 'Preserve frozen author review'
captures=json.loads((P/'run/captures.json').read_text())
cases={c['id']:c for c in json.loads((P/'preflight/cases.json').read_text())}
assert len(captures)==144
# Explicit inspected decisions, not a keyword classifier or generated judge.
stale={1,12,36}
wrong_owner={31,42,86,110,134}
ownership_negative={7,19,61,84,108,111,133,135}
withdrawal_negative={10,22,69,92,93,116,117,140,141}
withdrawal_ignored={35}
withdrawal_generalization={46}
old_value_repeated={26,47,52,54,68,70,71,77,94,95,100,102,119,127,143}
groups=[stale,wrong_owner,ownership_negative,withdrawal_negative,withdrawal_ignored,withdrawal_generalization,old_value_repeated]
assert sum(map(len,groups))==len(set().union(*groups))==42
answers=[]
for i,c in enumerate(captures):
    assert c['input_index']==i
    case=cases[c['id']]
    fields=dict.fromkeys(('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct'),True)
    reasons=[]
    if i in stale:
        for k in ('task_complete','source_consistent','supported_in_visible_state'):fields[k]=False
        reasons.append('The latest direct user assertion establishes the positive activity preference. With no withdrawal, update or elapsed-time premise, the answer invents a recency/reconfirmation requirement and abstains. This fails the frozen persistence convention.')
    if i in wrong_owner:
        for k in ('task_complete','source_consistent','supported_in_visible_state','ownership_correct'):fields[k]=False
        reasons.append('The question asks for the current user preference, which is unknown. The answer instead supplies the fictional character\'s preference as its affirmative/current-value response. Naming Rowan or Vale correctly in an explanation does not support that answer about the user or fulfill the requested ownership scope.')
    if i in withdrawal_negative:
        for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant'):fields[k]=False
        reasons.append('The answer gives a definite negative to a current-preference question after withdrawal. There is no later negative or alternative current value. Withdrawal establishes unknown, not a known absence or opposite of that preference.')
    if i in ownership_negative:
        for k in ('task_complete','source_consistent','supported_in_visible_state'):fields[k]=False
        reasons.append('The answer gives a definite negative or says the user has no preference, although the current user preference is unknown. Its explanation correctly distinguishes the fictional speaker, so ownership stays true; absence of a supported user preference does not establish a negative preference or lack of any preference.')
    if i in withdrawal_ignored:
        for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant'):fields[k]=False
        reasons.append('The answer supplies the old preference as current and says it has not been withdrawn, despite the explicit withdrawal in T2. The required current value is unknown.')
    if i in withdrawal_generalization:
        for k in ('source_consistent','supported_in_visible_state','withdrawal_compliant'):fields[k]=False
        reasons.append('The answer correctly makes the requested tea type unknown, but also asserts that the user currently prefers tea. This broader positive preference is unsupported after the sole preference record was withdrawn. The topic of the question does not reassert that preference.')
    if i in old_value_repeated:
        fields['withdrawal_compliant']=False
        reasons.append('The required current value or unknown answer is correct, but the explanation restates the withdrawn old preference. That historical statement is visible and supported, so source consistency and visible support stay true; the explicit current-scope output restriction fails.')
    if not reasons:
        if i in (76,101,124,125):
            reasons.append('Correctly denies the queried value because a different current preference is explicitly established. The named old value occurs in the direct current-state denial; the explanation refers to that detail without restating its old positive assignment. This satisfies the prospective distinction between a binary answer and forbidden old-value restatement.')
        elif i in (18,60,85,109,132):
            reasons.append('Correctly returns unknown for the user and attributes the only source preference to the fictional character. Its wording about unavailable current/recent information does not assert a known user preference or identify Vale as the user; no hidden reasoning is inferred from that wording.')
        elif case['kind']=='historical':
            reasons.append('Correctly answers at the explicitly requested original-passage scope. Quoting the withdrawn original value is allowed here. Additional textual/turn claims are supported; an uncited or clearly scoped first-person echo is not penalized.')
        elif case['kind']=='ownership':
            reasons.append('Correctly treats the current user preference as unknown and retains the source preference\'s fictional-speaker attribution.')
        else:reasons.append('Correctly supplies the latest supported user preference under the requested scope. Any explanation respects source ownership, withdrawal, later updates and the current-value output rule.')
    fields.update(body_valid=c['body_structurally_valid'],within_90_words=c['within_90_words'])
    evidence=[{'where':'answer','index':0,'quote':c['text']}]
    for turn,m in enumerate(case['history']):
        text=m['content'];evidence.append({'where':'history','index':turn,'quote':text})
        found=False
        for mi,message in enumerate(c['messages']):
            for quote in (text,json.dumps(text,ensure_ascii=False)[1:-1]):
                if quote in message['content']:
                    evidence.append({'where':'reader_message','index':mi,'quote':quote});found=True;break
            if found:break
        assert found,(i,turn)
    answers.append({'id':c['id'],'arm':c['arm'],**fields,'verdict':'pass' if all(fields.values()) else 'fail',
                    'reason':' '.join(reasons),'evidence':evidence})
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
review={'reviewer':'Codex, experiment author','model_version':'GPT-6','reviewed_at':datetime.now(timezone.utc).isoformat(),
    'status':'complete','process_notes':'Unblinded author review of all 144 captured answers against the frozen references, complete short histories and actual reader messages. Decision sets encode inspected judgments, not a keyword classifier. All answers were inspected after the 8B run completed. The same frozen criteria as the paired 4B review were applied. Every final answer has exact source and reader-message evidence. Required value correctness is separate from explanation compliance. Current-state binary denials are allowed when a different value is established; restating the old positive assignment in an explanation is not. Historical scope permits original quotes. Explicit wrong turn attributions are failures; missing citations are not. Naming a fictional speaker does not validate an affirmative answer about the user. No physical erasure or hidden reasoning is inferred. No independent validation or training-label admission is claimed.',
    'captures_sha256':sha(P/'run/captures.json'),'cases_sha256':sha(P/'preflight/cases.json'),
    'answers':answers,'training_labels':0}
(P/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print('Recorded all 144 author judgments; 102 strict pass, 42 fail')
