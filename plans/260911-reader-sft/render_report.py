"""Render the checked summary and all failure/correction evidence."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
read=lambda n:json.loads((HERE/n).read_text())

def render():
    s=read('summary.json');v=read('run/artifact-verification.json');t=read('run/training.json');status=read('run/status.json');bill=read('billing.json')
    caps=read('run/captures.json');ci={(c['id'],c['arm']):c for c in caps};cases={c['id']:c for c in read('preflight/eval-cases.json')};judgments=read('review.json')['answers']
    lines=['# Supervised 4B reader pilot: large gain, preservation rule fails','',
        'The single frozen answer-only LoRA pilot completed. Under unblinded author review, the trained reader passes all 48 new test questions and 93/96 regression questions, versus 35/48 and 70/96 for the base reader. The predeclared pilot rule **fails** because two previously correct regression answers become wrong. The saved adapter is an experimental artifact; this result does not admit retrieval-policy training or establish general reader readiness.','',
        '| Split | Base strict | Adapted strict | Base required answer | Adapted required answer |',
        '|---|---:|---:|---:|---:|']
    for split in ('regression','test','all'):
        a=s['counts'][split]['base'];b=s['counts'][split]['adapted'];n=a['n']
        lines.append(f"| {split} | {a['strict_pass']}/{n} | {b['strict_pass']}/{n} | {a['task_correct']}/{n} | {b['task_correct']}/{n} |")
    lines += ['', 'Strict passing requires all seven frozen criteria: required-answer correctness, source consistency, visible support for the whole answer, withdrawal compliance, ownership, body validity and at most 90 words. All 288 answers end at EOS, have valid bodies and meet the word cap; the longest is 56 words.', '',
        '## Prospective decision', '',
        '- New-test gain: **+13 strict passes**, exceeding the required +6.',
        '- Regression preservation: **FAIL**, with 25 strict corrections and two new failures.',
        '- Known-current-state answer preservation: **FAIL**, with the same two losses, N09-1 and N12-2.',
        '- Clean-suite gates: adapted **48/48 test PASS**, **93/96 regression FAIL**. Both base gates fail.', '',
        'The aggregate gain does not override the predeclared zero-regression requirements. No retry, alternate checkpoint, extra epoch, prompt revision or model sweep followed.', '',
        '## Every remaining adapted failure', '']
    for cid in s['failures']['adapted']:
        case=cases[cid];c=ci[cid,'adapted'];old=ci[cid,'base'];j=next(j for j in judgments if j['id']==cid and j['arm']=='adapted')
        lines += [f'### {cid}', '',f"Question: {case['query']}",'',f"Reference: {case['reference']['answer']}",'',f"Base: {old['text']}",'',f"Adapted: {c['text']}",'',j['reason'],'']
    lines += ['The N09 paired open question remains correct (MAH-ree), while its binary answer is contradictory. The N12 binary question correctly recalls the explicit no-preference statement, while its open question incorrectly reports unknown. These paired inconsistencies limit any claim that the adapter robustly tracks semantic state.', '',
        '## Judgment details and limits', '',
        'All 48 new base answers and all 144 adapted answers were inspected against full source histories, questions, references and reconstructed actual messages. All 96 base regression message/token/text sequences exactly reproduce the preceding diagnostic, and retain its checked author judgments. The review is unblinded and performed by the experiment author, not an independent evaluator. Evidence quotes and every criterion are saved in [review.json](review.json); explicit new decisions are in [review-decisions.json](review-decisions.json).', '',
        'The primary N01-1 judgment preserves the prior UNKNOWN-versus-No convention. Crediting its epistemic refusal-to-assert interpretation gives 71/96 base and 94/96 adapted strict regression passes. N09-1 and N12-2 still fail, so the pilot verdict is unchanged. This is the disclosed wording sensitivity, not a changed primary score.', '',
        'New base E18-open correctly states the negative ferry preference but adds an unsupported claim that it is not temporary. Its task answer passes and strict support fails. Generously accepting that extra claim would give 36/48 base strict test passes and a +12 adapted gain; the preservation failure is unchanged. E06-binary is accepted because Wednesday appears only in a current negation, with no restated old positive assignment. E24-binary explicitly repeats withdrawn language preferences and fails withdrawal compliance. Historical source echoes are allowed; an explicit statement of unknown alternatives is not required when a question asks only what negative preference is known.', '',
        '## Fixed supervision and execution', '',
        'The training set has 384 separately authored examples from 16 property/value families, 12 case types and binary/open forms (192 distinct histories). The new test has 48 questions on 24 separately handwritten families with properties and source/question wording absent from training. The earlier 96 cases remain regression-only. Exact train/eval history and question overlaps are zero, and train/new-test property overlap is zero. Related synthetic variants are not independent real-world samples; no population confidence interval or broad generalization claim is made.', '',
        'Before GPU execution, the author reviewed every training branch/template and all new test histories and references, ran all-case source/polarity invariants and five CPU tests, then froze data, order, configuration, source and the decision rule. Evaluation references, previous outputs and judgment code were not mounted in the GPU runtime. Baseline captures were collected before training, and semantic evaluation review began only after the fixed training finished.', '',
        'Model: Qwen/Qwen3-4B-Instruct-2507 at `cdbee75f17c01a7cc42f958dc650907174af0554`. LoRA rank 16, alpha 32, dropout 0.05, q_proj/v_proj across all 36 layers; 5,898,240 trainable adapter parameters. AdamW peak learning rate 1e-4, weight decay 0.01, microbatch one, accumulation sixteen, clipping 1.0, seed zero and two frozen shuffled epochs. All 48 optimizer steps and 768 example exposures completed; the fixed final step has zero learning rate, so 47 updates have nonzero learning rate. Mean answer loss by epoch was 1.0651 then 0.1393; this is training fit, not evaluation evidence.', '',
        'Only reviewed answer tokens and EOS contribute to loss: 9,448 target-token exposures, with 313,848 prefix-token exposures masked out. The supplied action prefix receives no loss. Frozen base parameters use BF16 during training, adapters FP32 and original buffers FP32, with non-reentrant gradient checkpointing. Evaluation uses the same original prompt, complete chronological history, forced ANSWER prefix, FP32 math attention, TF32 off, greedy decoding, fresh prefill and a 192-token output cap for both readers. Maximum evaluation input length is 464 tokens; this is not a long-context evaluation.', '',
        'Full base parameter/buffer hashes match before training, after training and after reloading. Adapter tensors changed and the saved final tensors exactly match the reloaded adapter. All 40 cached/fresh trajectory fixtures pass (20 actual prompts per reader). All 1,249 protected prior files remain unchanged. [Artifact verification](run/artifact-verification.json) checks source snapshots, masks, exposure order, finite adapter-only gradients, LR schedule, checkpoint hashes, output tokens and accounting.', '',
        f"The single H100 app `{read('run/launch.json')['app_id']}` is stopped with zero tasks. Its function completed in {status['elapsed_seconds']:.3f} seconds (hard limit 2,400; no retries), including {t['training_seconds']:.3f} seconds for the training phase through checkpoint save. Observed billing is **${bill['reported_total_usd']}**; billing is an observed snapshot and may lag. Training was 384 answer examples and zero routing labels.", '',
        '## Token and time accounting', '',
        '| Evaluation arm | Questions | Input tokens | Generated tokens including EOS | Actually forwarded tokens | Generation seconds |',
        '|---|---:|---:|---:|---:|---:|']
    for arm,a in v['accounting_by_arm'].items():
        lines.append(f"| {arm} | {a['calls']} | {a['input_tokens']:,} | {a['generated_tokens']:,} | {a['forwarded_tokens']:,} | {a['generation_seconds']:.3f} |")
    lines += ['', 'Generation time excludes cache fixtures, training, hashing, reload and artifact commits; the arms ran sequentially. The shorter adapted outputs reduce observed generation work, but this is not an end-to-end serving benchmark. Training sequence exposures total 323,296 tokens; backward/checkpoint recomputation is additional compute, not counted as new supervision.', '',
        '| Numerical fixtures | Count | Cached generated tokens | Cached forwarded tokens | Fresh generated tokens | Fresh forwarded tokens |',
        '|---|---:|---:|---:|---:|---:|']
    for arm,a in v['cache_gate_accounting_by_arm'].items():
        lines.append(f"| {arm} | {a['fixtures']} | {a['cached_generated_tokens']} | {a['cached_forwarded_tokens']:,} | {a['fresh_generated_tokens']} | {a['fresh_forwarded_tokens']:,} |")
    lines += ['', 'Fixture forward counts are reconstructed from frozen prompt lengths, captured trajectories and the exact runtime loop, including its last non-EOS forward. They are separate from answer-generation and training counts.', '',
        '## Scores by question form', '', '| Split/form | n | Base strict | Adapted strict | Base task | Adapted task |','|---|---:|---:|---:|---:|---:|']
    for split,groups in s['counts_by_form'].items():
        for kind,g in groups.items():
            a,b=g['base'],g['adapted'];lines.append(f"| {split}/{kind} | {a['n']} | {a['strict_pass']} | {b['strict_pass']} | {a['task_correct']} | {b['task_correct']} |")
    lines += ['', '## Scores by case type', '', '| Split/type | n | Base strict | Adapted strict | Base task | Adapted task |','|---|---:|---:|---:|---:|---:|']
    for split,groups in s['counts_by_kind'].items():
        for kind,g in groups.items():
            a,b=g['base'],g['adapted'];lines.append(f"| {split}/{kind} | {a['n']} | {a['strict_pass']} | {b['strict_pass']} | {a['task_correct']} | {b['task_correct']} |")
    lines += ['', '## Every paired correction and regression', '']
    for split,effects in s['matched_effects'].items():
        for metric,ids in effects.items():lines += [f"**{split}: {metric.replace('_',' ')} ({len(ids)})**: "+(', '.join(f'`{x}`' for x in ids) or 'none')+'.','']
    lines += ['All base and adapted failures, including required-answer-correct explanation failures, are reproduced in [ALL-FAILURES.md](ALL-FAILURES.md). Complete source evidence is in the review JSON.', '',
        '## Artifacts and interpretation', '',
        'The final adapter is [adapter_model.safetensors](run/adapter/adapter_model.safetensors), with [configuration](run/adapter/adapter_config.json). Its SHA-256 is `'+t['adapter_sha256']+'`. The [preflight plan](preflight/PLAN.md), [reference review](preflight/REFERENCE-REVIEW.md), [step log](run/training-steps.json), [reload proof](run/reload-verification.json), [summary](summary.json), [billing](billing.json) and [stopped app evidence](app-status.json) are retained. Reproduce local checks with `preflight/verify.py`, `verify_artifacts.py` and `verify_results.py` using the repository virtual environment.', '',
        'This fixed run is evidence that small supervised adaptation can substantially improve this short-history answer behavior, including new domains and wording. The two regressions prevent accepting the candidate under its own rule. It does not establish independent validation, long-history performance, production reliability, source-retrieval decisions, routing action generation or benchmark generalization. The experiment is closed with the checkpoint and failures preserved; another run would be a separately scoped experiment.', '']
    report='\n'.join(lines)
    failures=['# All strict failures','', 'These are the complete source-reviewed strict failures for both arms. Full histories and actual messages are retained in review.json.','']
    for j in judgments:
        if j['verdict']=='pass':continue
        c=ci[j['id'],j['arm']];case=cases[j['id']]
        failures += [f"## {j['arm']} / {j['id']}",'',f"Question: {case['query']}",'',f"Reference: {case['reference']['answer']}",'',f"Answer: {c['text']}",'',f"Required answer correct: {j['task_complete']}. Failed criteria: "+', '.join(k for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct','body_valid','within_90_words') if not j[k])+'.','',j['reason'],'']
    return {'REPORT.md':report,'ALL-FAILURES.md':'\n'.join(failures)}

if __name__=='__main__':
    for name,text in render().items():
        if (HERE/'result-manifest.json').exists():assert (HERE/name).read_text()==text
        else:(HERE/name).write_text(text)
    print('Rendered report and all failure records')
