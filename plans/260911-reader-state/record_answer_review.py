"""Record explicit author judgments after reading all 288 final answers."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
assert not (HERE/'result-manifest.json').exists()
captures=json.loads((HERE/'run/captures.json').read_text())
cases={c['id']:c for c in json.loads((HERE/'preflight/cases.json').read_text())}
old_c={c['id']:c for c in json.loads((HERE.parent/'260911-reader-repair/combined/captures.json').read_text()) if c['arm']=='baseline'}
old_j={c['id']:c for c in json.loads((HERE.parent/'260911-reader-repair/review.json').read_text())['answers'] if c['arm']=='baseline'}
FIELDS=('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct')

# Capture indices are explicit inspected decisions, not keyword-derived labels.
historical_denial={12,13,30,31,48,49,66,67}
wrong_owner={15,33,51,69,103,105,139,141,175,177,211,213}
withdrawal_negative={78,80,114,116,150,152,186,188,216,217,218,228,229,230,232,246,247,248,250,270,271,272}
ownership_negative={102,138,174,210}
unrelated_withdrawal={236,238}
wrong_none={282,283,285,287}
wrong_name_unknown={267}
right_no_wrong_explanation={265}
old_value_repeated={221}
groups=[historical_denial,wrong_owner,withdrawal_negative,ownership_negative,unrelated_withdrawal,
        wrong_none,wrong_name_unknown,right_no_wrong_explanation,old_value_repeated]
assert sum(map(len,groups))==len(set().union(*groups))
answers=[]
for i,c in enumerate(captures):
    case=cases[c['id']];reason=[]
    fields=dict.fromkeys(FIELDS,True)
    prompt_support=None if c['arm']=='baseline' else True
    if c['arm']=='baseline' and c['id'] in old_c:
        prior=old_c[c['id']]
        assert c['messages']==prior['messages'] and c['token_ids']==prior['token_ids'] and c['text']==prior['text']
        previous=old_j[c['id']];fields={k:previous[k] for k in FIELDS}
        reason.append('The actual messages, output tokens and answer text reproduce the prior 4B original arm exactly. The prior author judgment was checked against this saved answer and source and retained: '+previous['reason'])
    if i in historical_denial:
        fields['source_consistent']=fields['supported_in_visible_state']=False;prompt_support=False
        reason.append('The original fact is correctly recalled, but the answer also states without qualification that this detail was not withdrawn. The complete source contains the explicit T2 withdrawal, and the question itself presupposes it. The supplied original-passage record alone cannot support a claim of no withdrawal. Historical quoting remains permitted, so withdrawal_compliant stays true; the extra factual denial fails consistency/support.')
    if i in wrong_owner:
        for k in ('task_complete','source_consistent','supported_in_visible_state','ownership_correct'):fields[k]=False
        reason.append('The answer supplies the fictional character\'s preference as the current user preference, which is unknown. It faithfully follows the incorrectly user-owned positive state supplied by extraction, so state_prompt_supported remains true while underlying-source correctness and ownership fail.')
    if i in withdrawal_negative:
        for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant'):fields[k]=False
        if prompt_support is not None:prompt_support=False
        reason.append('The required current preference is unknown after withdrawal. The answer gives a leading No or asserts no preference, neither of which is established by withdrawal. An accompanying unknown explanation does not license the binary negative under the frozen scoring convention.')
        if i in {216,217,218}:
            reason.append('N01 asks whether a current-preference statement would be accurate. The primary judgment uses the frozen UNKNOWN-versus-negative convention. Because this wording also admits an epistemic refusal-to-assert reading, a separate sensitivity calculation must show the effect of accepting these three N01 binary answers; the captured answers and primary judgments remain unchanged.')
    if i in ownership_negative:
        for k in ('task_complete','source_consistent','supported_in_visible_state'):fields[k]=False
        prompt_support=False
        reason.append('The oracle record correctly says the user preference is unknown, but the answer gives No. This is an unsupported negative even when followed by an unknown explanation. It does not affirmatively assign the fictional preference to the user, so ownership remains true; there is no withdrawal in this case.')
    if i in unrelated_withdrawal:
        for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant'):fields[k]=False
        reason.append('The writing-tool preference remains fountain pen; only breakfast was withdrawn. The wrong unknown state comes from extraction applying an unrelated withdrawal. The answer fails the requested current preference and selective-withdrawal scope.')
        if i==236:
            prompt_support=False
            reason.append('It additionally converts its supplied unknown record into a leading No, so this answer also fails record-level support.')
        else:
            reason.append('Its unknown response faithfully follows the supplied wrong state; state_prompt_supported remains true.')
    if i in wrong_none:
        for k in ('task_complete','source_consistent','supported_in_visible_state'):fields[k]=False
        reason.append('The source explicitly establishes that the user has no preferred dessert. The answer either denies that explicit assertion or reports unknown. Known no-preference is distinct from missing information. There is no withdrawal and no other owner here.')
        if i in {282,287}:
            prompt_support=False
            reason.append('The oracle record has status known and polarity none, and its system instruction defines none as an explicit no-preference assertion. The answer contradicts even this correct supplied record.')
        elif i==283:
            prompt_support=False
            reason.append('The malformed extraction produced an unknown record, which still cannot support a definite denial that the user made the assertion.')
        else:
            reason.append('The unknown answer follows the fallback state from rejected extraction; it is record-faithful but source-incorrect.')
    if i in wrong_name_unknown:
        for k in ('task_complete','source_consistent','supported_in_visible_state'):fields[k]=False
        prompt_support=False
        reason.append('The user supplied MAH-ree at T0. Rejected extraction produced an unknown fallback, but the answer also incorrectly says the user has not provided the information. Unknown state does not support a never-provided claim. Both the requested pronunciation and the extra explanation fail.')
    if i in right_no_wrong_explanation:
        fields['source_consistent']=fields['supported_in_visible_state']=False;prompt_support=False
        reason.append('The leading binary No happens to be the correct requested response: MAY-ree was the assistant\'s version, not the user\'s supplied pronunciation. Required-answer correctness therefore stays true. However, the explanation falsely says whether MAY-ree was supplied is unknown; T0 and T1 establish the distinction. The supplied unknown fallback also does not license the leading No. This is one coincidentally correct binary response after invalid extraction, not successful state tracking.')
    if i in old_value_repeated:
        fields['withdrawal_compliant']=False
        reason.append('The answer correctly reports no current listed exercise preference, but its explanation restates the removed positive swimming preference. The source supports that historical statement; the current-scope withdrawal output restriction fails.')
    if not reason:
        if i in {96,98,132,134,168,170,204,206}:
            reason.append('Correctly recalls the original passage. The added wording about no indication of withdrawal is explicitly scoped to the supplied original-passage record, which indeed contains only T0. This is distinguished from the unqualified claim that the detail was not withdrawn in the D-series failures. The value remaining as stated is read at the requested historical-passage scope, not as an unexpressed current-user assertion.')
        elif i in {6,24,222,227}:
            reason.append('Correctly answers the negative enjoyment question from the visible negative wording. The extracted record violates the signed activity-value convention, but the full negative sentence remains present and the reader recovers the source-correct answer. This does not repair or validate the extraction; required answer and state-contract correctness are separate.')
        elif case['scope']=='historical':
            reason.append('Correctly answers the explicitly identified original passage. Historical scope allows the old value; the answer does not assert it as the current preference. This control bypasses event extraction.')
        else:
            reason.append('Correctly answers from the supported current user state. It respects owner, explicit negative versus unknown/no-preference, later updates and relevant withdrawal boundaries. Any explanation is supported and respects the requested scope. First-person wording that directly echoes the user\'s question is not treated as assistant biography.')
    fields.update(body_valid=c['body_structurally_valid'],within_90_words=c['within_90_words'])
    evidence=[{'where':'answer','index':0,'quote':c['text']},
              {'where':'reader_message','index':1,'quote':c['messages'][1]['content']}]
    evidence.extend({'where':'history','index':j,'quote':m['content']} for j,m in enumerate(case['history']))
    answers.append({'id':c['id'],'arm':c['arm'],**fields,'state_prompt_supported':prompt_support,
        'verdict':'pass' if all(fields.values()) else 'fail','reason':' '.join(reason),'evidence':evidence})
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
review={'status':'complete','reviewer':'Codex, experiment author','model_version':'GPT-6',
    'reviewed_at':datetime.now(timezone.utc).isoformat(),
    'process_notes':'Unblinded author inspection of all 288 answers, their source histories and reconstructed actual messages after collection. The 72 exactly reproduced prior baseline answers retain their checked prior author judgments. State support is scored separately from correctness against the underlying full source. Required-answer correctness is separate from explanatory errors, including N09\'s accidental correct No. UNKNOWN-versus-No follows the frozen convention; N01\'s epistemic wording is explicitly flagged for sensitivity. Historical claims are interpreted at their expressed scope: no withdrawal in the supplied original-passage record differs from an unqualified assertion that the detail was not withdrawn. First-person echoes are permitted. No hidden reasoning or independent review is inferred. No training labels are admitted.',
    'captures_sha256':sha(HERE/'run/captures.json'),'cases_sha256':sha(HERE/'preflight/cases.json'),
    'prior_review_sha256':sha(HERE.parent/'260911-reader-repair/review.json'),'answers':answers,'training_labels':0}
(HERE/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print('Recorded all 288 judgments:',sum(a['verdict']=='pass' for a in answers),'strict pass;',sum(a['task_complete'] for a in answers),'required answers correct')
