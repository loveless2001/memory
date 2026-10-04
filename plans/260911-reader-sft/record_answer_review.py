"""Materialize explicit author decisions after source-based answer inspection."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
FIELDS=('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct')
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert not (HERE/'result-manifest.json').exists()
    decisions=read(HERE/'review-decisions.json');assert decisions['review_complete']
    caps=read(HERE/'run/captures.json');cases={c['id']:c for c in read(HERE/'preflight/eval-cases.json')}
    prior=HERE.parent/'260911-reader-state'
    old_c={c['id']:c for c in read(prior/'run/captures.json') if c['arm']=='baseline'}
    old_j={j['id']:j for j in read(prior/'review.json')['answers'] if j['arm']=='baseline'}
    answers=[];used=set()
    for c in caps:
        key=c['arm']+':'+c['id'];case=cases[c['id']]
        fields=dict.fromkeys(FIELDS,True)
        if c['arm']=='base' and case['split']=='regression':
            oc=old_c[c['id']];oj=old_j[c['id']]
            assert all(c[k]==oc[k] for k in ('messages','token_ids','text'))
            fields={k:oj[k] for k in FIELDS}
            reason='Exact prior baseline messages, token sequence and text verified; retain the prior source-checked author judgment. '+oj['reason']
        else:
            assert key in decisions['answers'],key
            d=decisions['answers'][key];used.add(key)
            for k in d['failed_fields']:assert k in FIELDS;fields[k]=False
            reason=d['reason']
        fields.update(body_valid=c['body_structurally_valid'],within_90_words=c['within_90_words'])
        evidence=[{'where':'answer','index':0,'quote':c['text']},{'where':'reader_message','index':1,'quote':c['messages'][1]['content']}]
        evidence.extend({'where':'history','index':i,'quote':m['content']} for i,m in enumerate(case['history']))
        answers.append({'id':c['id'],'arm':c['arm'],**fields,'verdict':'pass' if all(fields.values()) else 'fail','reason':reason,'evidence':evidence})
    assert used==set(decisions['answers']) and len(used)==192 and len(answers)==288
    result={'status':'complete','reviewer':'Codex, experiment author','model_version':'GPT-6','reviewed_at':datetime.now(timezone.utc).isoformat(),
        'process_notes':'Unblinded author review of all 48 new baseline answers and all 144 adapted answers against complete source histories, questions, references and actual supplied messages. The 96 exactly reproduced prior baseline outputs retain their source-checked author judgments after exact message/token/text verification. All new decisions are explicit inspected judgments, not keyword-derived scores. Required-answer correctness is separate from explanation support. Historical quoting and source-grounded first-person echoes are permitted. Negative answers after withdrawal remain errors under the frozen convention; N01 wording sensitivity is separate. No evaluation answers were training targets, and semantic review began only after fixed training completed. This is not independent validation.',
        'captures_sha256':sha(HERE/'run/captures.json'),'cases_sha256':sha(HERE/'preflight/eval-cases.json'),
        'prior_review_sha256':sha(prior/'review.json'),'decisions_sha256':sha(HERE/'review-decisions.json'),'answers':answers}
    (HERE/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'reviewed':len(answers),'strict_pass':sum(j['verdict']=='pass' for j in answers),'task_correct':sum(j['task_complete'] for j in answers)}))
if __name__=='__main__':main()
