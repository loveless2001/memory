"""Record explicit author decisions after inspection of all 144 saved answers."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
P=Path(__file__).resolve().parent
assert not (P/'result-manifest.json').exists(), 'Preserve frozen author review'
captures=json.loads((P/'combined/captures.json').read_text())
cases={c['id']:c for c in json.loads((P/'preflight/cases.json').read_text())}
assert len(captures)==144
# Explicit inspected decisions, not a keyword classifier or generated judge.
stale={1,12}
wrong_owner={7,19,30,31,42,61,62,84,87,108,109,111,133,135}
withdrawal_negative={10,11,22,23,68,69,92,93,116,117,140,141}
ignored_later={89,112}
old_value_repeated={26,34,35,38,46,47,54,70,71,77,78,94,95,102,118,119,125,127,142,143}
wrong_ack_turn={129}
groups=[stale,wrong_owner,withdrawal_negative,ignored_later,old_value_repeated,wrong_ack_turn]
assert sum(map(len,groups))==len(set().union(*groups))==51
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
    if i in ignored_later:
        for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant'):fields[k]=False
        reasons.append('T4 explicitly re-establishes the same value after the T2 withdrawal. The answer acknowledges the later reassertion but still prioritizes the earlier withdrawal, producing the wrong negative and an unsupported chronology/precedence explanation.')
    if i in old_value_repeated:
        fields['withdrawal_compliant']=False
        reasons.append('The required current value or unknown answer is correct, but the explanation restates the withdrawn old preference. That historical statement is visible and supported, so source consistency and visible support stay true; the explicit current-scope output restriction fails.')
        if i==77:reasons.append('The clause that it was the preferred activity restates the old assignment through the immediately preceding origami antecedent; this goes beyond a direct current-state No.')
    if i in wrong_ack_turn:
        fields['source_consistent']=False;fields['supported_in_visible_state']=False
        reasons.append('The requested original preference is correct, but the answer explicitly locates acknowledgment of the withdrawal in T2. T2 is the user request; the assistant acknowledgment is T3. The incorrect explanatory turn attribution fails whole-answer source consistency and support.')
    if not reasons:
        if i in (52,100):
            reasons.append('Correctly denies the queried value because a different current preference is explicitly established. The named old value occurs in the direct current-state denial; the explanation refers to that detail without restating its old positive assignment. This satisfies the prospective distinction between a binary answer and forbidden old-value restatement.')
        elif i==132:
            reasons.append('Correctly returns unknown for the user and attributes the only source preference to Vale. Its wording about unavailable current/recent information does not assert a known user preference or identify Vale as the user; no hidden reasoning is inferred from that wording.')
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
    'status':'complete','process_notes':'Unblinded author review of all 144 captured answers against the frozen references, complete short histories and actual reader messages. Decision sets encode inspected judgments, not a keyword classifier. The first 35 were inspected while the unchanged continuation ran. Every final answer has exact source and reader-message evidence. Required value correctness is separate from explanation compliance. Current-state binary denials are allowed when a different value is established; restating the old positive assignment in an explanation is not. Historical scope permits original quotes. Explicit wrong turn attributions are failures; missing citations are not. Naming a fictional speaker does not validate an affirmative answer about the user. No physical erasure or hidden reasoning is inferred. No independent validation or training-label admission is claimed.',
    'captures_sha256':sha(P/'combined/captures.json'),'cases_sha256':sha(P/'preflight/cases.json'),
    'answers':answers,'training_labels':0}
(P/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print('Recorded all 144 author judgments; 93 strict pass, 51 fail')
