"""Render verified aggregate results and every strict failure."""
import json,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent
read=lambda n:json.loads((HERE/n).read_text())

def render():
    s=read('summary.json');v=read('run/artifact-verification.json');t=read('run/training.json');status=read('run/status.json');billing=read('billing.json')
    caps=read('run/captures.json');ci={(c['id'],c['arm']):c for c in caps};cases={c['id']:c for c in read('preflight/eval-cases.json')};js=read('review.json')['answers']
    rule=s['predeclared_followup_rule'];verdict='PASS' if rule['pass'] else 'FAIL'
    lines=[f'# Revised-supervision 4B reader pilot: {verdict}', '',
        f'The single revised-data pilot completed all 64 optimizer steps and 416 answer captures. The predeclared follow-up rule is **{verdict}** under unblinded author review. Scores below compare the frozen v1 adapter with the newly trained and reloaded v2 adapter on identical messages. The original v1 experiment remains frozen with its original failed verdict.', '',
        '| Split | v1 strict | v2 strict | v1 required answer | v2 required answer |','|---|---:|---:|---:|---:|']
    for split in ('regression','test','all'):
        a,b=s['counts'][split]['prior'],s['counts'][split]['adapted'];n=a['n']
        lines.append(f"| {split} | {a['strict_pass']}/{n} | {b['strict_pass']}/{n} | {a['task_correct']}/{n} | {b['task_correct']}/{n} |")
    lines += ['', 'The regression set contains all 144 previously evaluated questions, including the former 48-question test. It is reused evaluation after those results informed the revision. Only the new 64 questions are a fresh test for this follow-up; they comprise four related questions per sixteen separately authored histories.', '',
        '## Predeclared acceptance rule', '',
        f"- Fix N09-1 and N12-2: **{'PASS' if rule['both_known_failures_fixed'] else 'FAIL'}**; individual strict results: "+', '.join(f"{k}={'pass' if x else 'fail'}" for k,x in rule['known_failures_fixed'].items())+'.',
        f"- Preserve all 141 v1 regression strict passes: **{'PASS' if rule['regression_preservation_pass'] else 'FAIL'}**. Lost cases: "+(', '.join(rule['regression_strict_pass_to_fail']) or 'none')+'.',
        f"- Preserve all earlier raw-base-correct required answers and all v1-correct required answers on the new test: **{'PASS' if rule['required_answer_preservation_pass'] else 'FAIL'}**. Earlier raw-base losses: "+(', '.join(rule['raw_base_required_answer_losses']) or 'none')+'; new-test losses: '+(', '.join(rule['new_test_required_answer_losses']) or 'none')+'.',
        f"- New-test floor 60/64: **{'PASS' if rule['new_test_floor_pass'] else 'FAIL'}** ({rule['new_test_strict']}/64).",
        f"- New-test strict score at least v1: **{'PASS' if rule['new_test_non_degradation_pass'] else 'FAIL'}**.", '',
        'Separate perfect-suite gates: '+'; '.join(f"{arm}: "+', '.join(f"{split}={'PASS' if passed else 'FAIL'}" for split,passed in gates.items()) for arm,gates in s['clean_suite_gates'].items())+'.', '',
        'The pilot threshold is not a production-readiness standard. No result here admits retrieval-policy training, routing action generation, long-history reliability or deployment.', '',
        '## Known failure pairs and remaining errors', '']
    for cid in ('N01-1','N09-1','N09-2','N12-1','N12-2'):
        a,b=ci[cid,'prior'],ci[cid,'adapted'];case=cases[cid]
        j=next(j for j in js if j['id']==cid and j['arm']=='adapted')
        lines += [f'**{cid}** — '+case['query'],'',f"Reference: {case['reference']['answer']}",'',f"v1: {a['text']}",'',f"v2: {b['text']}",'',f"v2 strict: {j['verdict']}. "+j['reason'],'']
    lines += ['The new test improves by four required-answer corrections, all in explicit-none or known-negative coverage. H02-1 still shows the same binary contradiction on a new surname, while code, numeric-suffix and entrance comparisons pass. This supports a narrow improvement rather than a general repair of assertion comparison.', '',
        'H09-4 is a new strict-only failure: it turns not preferred into an explicit rejection. The required negative and unknown-alternative answer remains correct. Generously interpreting reject as reject-as-the-preferred-option yields 63/64 v2 strict test passes instead of 62/64, with no new strict test regression. The two required target failures still leave the prospective rule failed. E18 negative-preference paraphrases retain the earlier interpretation and introduce no categorical refusal or duration claim.', '',
        'For N12-2, the v2 claim that no particular preferred dessert was specified can be literally true; support stays true, but the answer omits the explicitly known no-preference state. Likewise, H11-4 in v1 supplies only the unknown alternative and omits the known negative. Required-answer completeness and source consistency are scored separately.', '',
        'All four new-test questions pass within '+str(sum(s['all_four_test_questions_pass_by_family']['prior'].values()))+'/16 families for v1 and '+str(sum(s['all_four_test_questions_pass_by_family']['adapted'].values()))+'/16 for v2 under primary strict scoring. These are related question groups, not independent reliability estimates.', '']
    lines += ['All remaining v2 strict failures: '+(', '.join('`'+c+'`' for c in s['failures']['adapted']) or 'none')+'.', '',
        'Every v1 and v2 strict failure is reproduced with its question, reference, answer and judgment in [ALL-FAILURES.md](ALL-FAILURES.md). The [complete review](review.json) retains exact full-history and actual-message evidence for every answer. Binary/open answers sharing a history are scored individually; conflicting paired answers cannot be rescued by selecting the better form.', '',
        '## Supervision, isolation and interpretation', '',
        'The revision retains all 384 original training cases unchanged and adds 128 new cases: 64 user-assertion comparisons across eight factual families, with and without assistant conflicts, and 64 positive/none/negative/withdrawn preference contrasts across eight additional families. There are 512 examples, 32 families and 240 distinct histories. Prior evaluation histories, questions and model answers are excluded from training. The test uses sixteen new properties absent from all training and prior evaluation; exact train/eval history and query overlaps are zero.', '',
        'The author reviewed the two new training constructors, all sixteen new training family definitions, every new test history and all 64 test references before freezing. All-case evidence-role/bounds, polarity, scope, target-length and overlap checks passed, as did the five answer-mask/precision CPU tests. This is author review plus mechanical checks, not independent validation.', '',
        'The coverage gaps motivate this experiment but are not proven causes of the earlier failures. V2 is trained from the original base, using two epochs of the expanded mixture. Compared with v1 it also has more optimizer steps, different shuffled orders and a longer LR schedule. The result compares these complete recipes; it does not isolate the causal effect of the added examples. The synthetic families and four related questions per test history do not justify population or real-world reliability claims.', '',
        'All 144 v1 regression message/token/text sequences reproduce exactly and retain their source-checked prior judgments. All 64 new v1 answers and all 208 v2 answers receive new unblinded author review against complete histories, questions, references and reconstructed actual prompts. Semantic evaluation review began after the fixed training finished. The N01 wording ambiguity retains its frozen primary judgment; the separate generous sensitivity is shown below and does not alter the primary rule.', '',
        '| N01 sensitivity | Regression strict | Regression required answer |','|---|---:|---:|']
    for arm,a in s['n01_sensitivity']['counts'].items():lines.append(f"| {arm} | {a['regression_strict_pass']}/144 | {a['regression_task_correct']}/144 |")
    cfg=read('preflight/runtime-config.json');steps=read('run/training-steps.json')
    lines += ['', '## Fixed runtime and integrity', '',
        'Qwen/Qwen3-4B-Instruct-2507 revision `'+cfg['model_revision']+'`; Torch 2.7.1, Transformers 4.55.2 and PEFT 0.17.0. LoRA rank 16/alpha 32/dropout .05 on q_proj and v_proj in all 36 layers, 5,898,240 trainable parameters. Seed zero, AdamW peak LR 1e-4/weight decay .01, microbatch one, accumulation sixteen and clipping 1. Three-step warmup and linear decay end at LR zero on step 64; 63 steps have nonzero LR. No checkpoint selection or early stopping. Epoch mean answer losses: '+', '.join(f"{statistics.mean(x['mean_answer_loss'] for x in steps if x['epoch']==e):.6f}" for e in (1,2))+'. These are training-fit measures.', '',
        f"All 1,024 example exposures completed. Answer/EOS target exposures: {t['answer_target_tokens']:,}; masked prefix exposures: {t['masked_prefix_tokens']:,}. No routing or supplied ANSWER-prefix loss is trained. BF16 frozen base parameters, FP32 adapter parameters and original FP32 buffers are used for training, with non-reentrant gradient checkpointing. Evaluation uses FP32 math attention, TF32 disabled, original answer-only prompt, full chronological history, fresh prefill, greedy decoding and a 192-token/90-word cap.", '',
        'The comparator reads only the two hash-pinned prior adapter files. A dedicated output volume keeps old model captures and evaluation references outside the runtime mounts. Training references are intentionally mounted as supervision; evaluation references and review code are not. All base parameter and buffer hashes are unchanged across training/reload, adapter weights changed, and saved/reloaded adapter tensors are exactly equal. All 40 cached/fresh checks pass. All '+str(v['protected_files_unchanged'])+' protected files remain unchanged.', '',
        f"The single app `{read('run/launch.json')['app_id']}` is stopped with zero tasks. Function time: {status['elapsed_seconds']:.3f} s; training phase through save: {t['training_seconds']:.3f} s. Hard limit 2,400 seconds, internal limit 2,300 seconds, no retries. Observed cost: **${billing['reported_total_usd']}**, a billing snapshot that can lag execution. No automatic follow-up run occurred.", '',
        '## Accounting', '', '| Arm | Answers | Input tokens | Generated tokens incl. EOS | Forwarded tokens | Generation seconds |','|---|---:|---:|---:|---:|---:|']
    for arm,a in v['accounting_by_arm'].items():lines.append(f"| {arm} | {a['calls']} | {a['input_tokens']:,} | {a['generated_tokens']:,} | {a['forwarded_tokens']:,} | {a['generation_seconds']:.3f} |")
    lines += ['',f"All {len(caps)} answers ended at EOS: {sum(c['ended_at_eos'] for c in caps)==len(caps)}. Valid bodies: {v['body_valid_answers']}; within 90 words: {v['answers_within_90_words']}; maximum words: {max(c['word_count_whitespace'] for c in caps)}. Maximum input is {read('preflight/cpu-checks.json')['max_eval_input_tokens']} tokens. Training prefix/target exposures exclude backward and gradient-checkpoint recomputation; generation seconds exclude training, hash/reload checks, numerical fixtures and commits. This is not a serving benchmark.", '',
        '| Fixture arm | Count | Cached generated | Cached forwarded | Fresh generated | Fresh forwarded |','|---|---:|---:|---:|---:|---:|']
    for arm,a in v['cache_gate_accounting_by_arm'].items():lines.append(f"| {arm} | {a['fixtures']} | {a['cached_generated_tokens']} | {a['cached_forwarded_tokens']} | {a['fresh_generated_tokens']} | {a['fresh_forwarded_tokens']} |")
    lines += ['', 'Fixture forwarded-token counts are reconstructed from the frozen runtime loop and captured trajectories, including the last non-EOS forward. They are separate from evaluation and training counts.', '']
    for title,key in [('Question form','counts_by_form'),('Case type','counts_by_kind')]:
        lines += ['## '+title,'','| Split/category | n | v1 strict | v2 strict | v1 task | v2 task |','|---|---:|---:|---:|---:|---:|']
        for split,groups in s[key].items():
            for name,g in groups.items():
                a,b=g['prior'],g['adapted'];lines.append(f"| {split}/{name} | {a['n']} | {a['strict_pass']} | {b['strict_pass']} | {a['task_correct']} | {b['task_correct']} |")
        lines.append('')
    lines+=['## Every correction and regression','']
    for split,effects in s['matched_effects'].items():
        for name,ids in effects.items():lines += [f"**{split} {name.replace('_',' ')} ({len(ids)})**: "+(', '.join('`'+x+'`' for x in ids) or 'none')+'.','']
    lines += ['## Saved artifacts','',
        'The final [adapter weights](run/adapter/adapter_model.safetensors) have SHA-256 `'+t['adapter_sha256']+'`. The [plan](preflight/PLAN.md), [reference review](preflight/REFERENCE-REVIEW.md), [step log](run/training-steps.json), [reload proof](run/reload-verification.json), [artifact verification](run/artifact-verification.json), [summary](summary.json), [billing](billing.json) and [app state](app-status.json) are retained. Use `preflight/verify.py`, `verify_artifacts.py` and `verify_results.py` with the repository virtual environment for local verification.','']
    failures=['# Every strict failure','', 'Full source histories and actual prompts are attached to each judgment in review.json.','']
    for j in js:
        if j['verdict']=='pass':continue
        c=ci[j['id'],j['arm']];case=cases[j['id']]
        failures += [f"## {j['arm']} / {j['id']}",'',f"Question: {case['query']}",'',f"Reference: {case['reference']['answer']}",'',f"Answer: {c['text']}",'',f"Required answer correct: {j['task_complete']}. "+j['reason'],'']
    return {'REPORT.md':'\n'.join(lines),'ALL-FAILURES.md':'\n'.join(failures)}
if __name__=='__main__':
    for name,text in render().items():
        if (HERE/'result-manifest.json').exists():assert (HERE/name).read_text()==text
        else:(HERE/name).write_text(text)
    print('Rendered report and full failure inventory')
