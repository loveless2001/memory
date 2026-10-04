"""Render the frozen matched-supervision result and every strict failure."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
read=lambda n:json.loads((HERE/n).read_text())
ARMS=['current_direct','current_decision','trained_direct','trained_decision']
def render():
 s=read('summary.json');review=read('review.json');status=read('run/status.json');bill=read('billing.json');launch=read('run/launch.json');cfg=read('preflight/runtime-config.json')
 decisions=read('review-decisions.json');notes=decisions.get('result_notes',[])
 out=['# Structured-decision supervision: matched four-condition experiment','',f"**Prospective result: {s['verdict']}.**",'']
 out+=[line for note in notes for line in (note,'')]+['All scores below use the frozen source references and unblinded author review. This is a selected synthetic pilot with forty new histories, not independent external validation. Both new continuations started from the same frozen v2 checkpoint; ordinary prose and structured targets used the same 512 source/question pairs and 64 updates.','',
 '## Main results','',
 '| Condition | New strict /160 | New rendered-only strict /160 | New required answer /160 | Regression strict /260 | Protected regression losses /259 |','|---|---:|---:|---:|---:|---:|']
 for a in ARMS:
  t=s['scores']['test'][a];r=s['scores']['regression'][a];p=s['scores']['protected_regression'][a]
  out.append(f"| {a} | {t['strict_correct']} | {t['rendered_strict_correct']} | {t['required_answer_correct']} | {r['strict_correct']} | {len(p['strict_failures'])} |")
 out+=['',
 'Strict scores require the prior seven final-answer criteria. Decision arms additionally require usable schema, correct state/scope/relation, query interpretation, decision, evidence and ownership. Rendered-only correctness omits those additional record criteria; it cannot rescue a wrong record for the primary decision. Invalid records fail even if the correct response would have been unknown.','',
 'The four conditions are: current v2 with its original answer prompt; current v2 with the structured prompt and deterministic renderer; v2 continued on ordinary answers; and v2 independently continued on structured decisions. Each condition receives only the complete archive and question. Prose/decision user messages are identical; system instructions and output targets differ. No oracle property, candidate, scope, state or query interpretation is supplied at inference.','',
 '## Frozen pass rule','', '| Requirement | Result |','|---|---|']
 for name,passed in s['predeclared_gates'].items():out.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
 out+=['',
 'The 95% threshold is 152/160. The trained decision model must strictly exceed both current-direct and trained-direct new-test scores and lose none of the 259 protected regression cases. The protection mask is the union of previously strict-correct non-oracle answers on exact matching histories/questions across the prior seven experiments. It includes previous model sizes, prompts and extracted pipelines. N01-1 is the only regression without such a prior pass; it is still evaluated. No score threshold was changed after inference.','',
 'Protected regression losses for trained_decision: '+(', '.join(s['protected_regression_loss_ids']) or 'none')+'.','',
 '## Matched changes on the new questions','',
 '| Comparison | Strict corrections / regressions | Rendered corrections / regressions | Required-answer corrections / regressions |','|---|---:|---:|---:|']
 for pair,by_split in s['matched_transitions'].items():
  counts=[]
  for metric in ('strict','rendered','required'):
   x=by_split['test'][metric];counts.append(f"{len(x['corrected'])} / {len(x['regressed'])}")
  out.append('| '+pair+' | '+' | '.join(counts)+' |')
 out+=['','All new-test and regression transitions, including every corrected and regressed ID, are retained in summary.json. [ALL-FAILURES.md](ALL-FAILURES.md) contains every strict failure with raw output, rendered answer, source, original reference and the author judgment.','',
 '## Structured record accuracy','', '| Condition / split | Schema valid | State correct | Query interpretation correct | Decision correct | Evidence sufficient | Ownership correct | Full semantic record correct |','|---|---:|---:|---:|---:|---:|---:|---:|']
 for split in ('test','regression'):
  for a in ('current_decision','trained_decision'):
   x=s['scores'][split][a];rc=x['record_criteria_passes'];out.append('| '+a+' / '+split+' | '+str(x['schema_valid'])+' | '+' | '.join(str(rc[k]) for k in ('state_correct','query_interpretation_correct','decision_correct','evidence_sufficient','record_ownership_correct'))+' | '+str(x['record_semantically_correct'])+' |')
 out+=['',
 'On the new questions, exact full canonical record agreement (all nine fields, ignoring JSON key order/whitespace) is '+', '.join(f"{a}: {z['exact_full_record']}/160" for a,z in s['new_literal_record_agreement'].items())+'. Exact agreement on the seven semantic fields excluding turn/quote is '+', '.join(f"{a}: {z['exact_semantic_fields']}/160" for a,z in s['new_literal_record_agreement'].items())+'. These literal diagnostics do not replace context-sensitive author review; sufficient alternative quotes and semantically equivalent value phrases can still be correct.',
 '',
 'A schema/span check only establishes that fields and copied strings have valid locations. It does not establish whose fact is expressed, whether a withdrawal controls, whether an alternative candidate remains unknown, or whether the binary decision is correct. Source-grounded semantic equivalence is judged separately from exact canonical text. Internal candidate fields and current-source quotes are not displayed as final answers. Given correctly scoped records, the renderer preserves unknown and historical scope without repeating withdrawn values in current answers; it cannot correct wrongly encoded current facts.','',
 '## New-test breakdown','', '| History type | Questions | Current direct | Current decision | Trained direct | Trained decision |','|---|---:|---:|---:|---:|---:|']
 for name,arms in s['scores'].items():
  if name.startswith('test:kind:'):out.append('| '+name.split(':')[-1]+' | '+str(arms['current_direct']['total'])+' | '+' | '.join(str(arms[a]['strict_correct']) for a in ARMS)+' |')
 out+=['',
 'All four questions on a new history are strictly correct for '+', '.join(f"{a}: {s['new_histories_all_four_strict_correct'][a]}/40" for a in ARMS)+'.','',
 '| Trained-decision comparison | Mean strict accuracy difference | Descriptive 95% history-bootstrap interval |','|---|---:|---|']
 for baseline,z in s['new_history_clustered_differences'].items():
  lo,hi=z['descriptive_95pct_percentile_interval'];out.append(f"| versus {baseline} | {100*z['mean_accuracy_difference']:.2f} pp | [{100*lo:.2f}, {100*hi:.2f}] pp |")
 out+=['',s['interval_caveat'],'',
 '## Training and inference accounting','',
 'Each continuation sees the same 512 examples twice, in the same two frozen shuffled orders. Each uses 64 optimizer steps, including the same final zero-LR step of the existing linear schedule. Starting adapter files/tensors are identical; no checkpoint from one continuation initializes the other. The LoRA shape, optimizer, seed and update count are matched. Target lengths, system prompt lengths, dropout draw shapes, computation and elapsed times differ. This tests the complete supervision recipe; it is not a matched-FLOP or isolated-format causal estimate.','',
 '| Continuation | Exposures | Updates | Supervised target tokens | Masked prefix tokens | Training seconds | Adapter SHA-256 |','|---|---:|---:|---:|---:|---:|---|']
 for a,t in s['training'].items():out.append(f"| {a} | {t['examples_seen']} | {t['optimizer_steps']} | {t['answer_target_tokens']} | {t['masked_prefix_tokens']} | {t['training_seconds']:.3f} | {t['adapter_sha256']} |")
 out+=['',
 '| Evaluation condition | Calls | Input tokens | Generated tokens | Forwarded tokens | Generation seconds |','|---|---:|---:|---:|---:|---:|']
 for a in ARMS:
  z=s['verification']['accounting_by_arm'][a];out.append(f"| {a} | {z['calls']} | {z['input_tokens']} | {z['generated_tokens']} | {z['forwarded_tokens']} | {z['generation_seconds']:.3f} |")
 out+=['',
 'Prose has a 192-token generation cap; structured output has a 256-token cap for its nine fields and source quote. Both final answer formats have a 90-word limit. All calls use fresh prefill, greedy decoding, FP32 math attention and TF32 off. Gate token accounting is separately retained in summary.json. Generation seconds exclude loading, training, commits, local rendering/review and other overhead, so this is not a serving latency benchmark.','',
 f"App [{launch['app_id']}](https://modal.com/apps/syntracts/main/{launch['app_id']}) completed in {status['elapsed_seconds']:.3f} function seconds. One H100, four CPUs, 32 GiB RAM; 3,600-second hard ceiling and zero retries. Observed billing is **${bill['reported_total_usd']}** at {bill['observed_at']}; billing can lag. The app is stopped with zero tasks.",'',
 '## Verification and limits','',
 f"All {s['verification']['captures']} captures and {s['verification']['passed_cache_checks']}/80 cached/fresh fixtures completed. All 260 prior direct prompts, token sequences and texts reproduce exactly. Both trainings have finite loss/gradients, exact exposure order, target-only supervision and adapter-only updates. Complete base parameters/buffers stayed unchanged; both saved adapters reload exactly and their tensors remain unchanged after inference. All {s['verification']['protected_files']} protected prior files are unchanged.",'',
 'Training has sixteen novel properties across eight history types (120 distinct histories); the forty test properties and their exact histories/questions are disjoint from this training, prior training and regression. Four related questions share each new history. The synthetic templates and author review limit generalization. Correct enum output and correct rendering do not prove an internal reasoning mechanism or reliable long-context retrieval.','',
 'The categorical-No versus unknown rule from prior evaluations remains primary. Alternative epistemic readings, if applicable, are disclosed in review decisions without changing primary verdicts. Scope, polarity and factual support are evaluated against full source, not a keyword-based Yes/No score.','']
 out+=decisions.get('interpretation_notes',[])+['',
 'Artifacts: [frozen plan](preflight/PLAN.md), [reference review](preflight/REFERENCE-REVIEW.md), [review](review.json), [explicit decisions](review-decisions.json), [rendered decisions](rendered-decisions.json), [summary](summary.json), [verification](run/artifact-verification.json). Reproduce the final checks with `.venv/bin/python plans/260911-reader-decision/verify_results.py`. No follow-up run was launched.','']
 fails=['# Complete strict-failure inventory','','Passing and failing records are both retained in review.json. This inventory uses the frozen primary criteria.']
 for j in review['answers']:
  if j['verdict']=='pass':continue
  e=j['evidence'];fields=[k for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct','body_valid','within_90_words') if not j[k]]
  if j['record_criteria'] is not None:fields += ['record:'+k for k,v in j['record_criteria'].items() if not v]
  if j['schema_valid'] is False:fields.append('schema_valid')
  fails+=['',f"## {j['arm']} / {j['id']}",'','Question: '+e['query'],'','Raw model output:','```',e['raw_model_text'],'```','','Rendered answer: '+e['rendered_answer'],'','Reference: '+e['reference']['answer'],'','Failed criteria: '+', '.join(fields)+'.','',j['reason'],'','Source:']
  fails += [f"- T{i} {m['role']}: {m['content']}" for i,m in enumerate(e['history'])]
  if e['parsed_record'] is not None:fails+=['','Parsed record: `'+json.dumps(e['parsed_record'],ensure_ascii=False)+'`']
 return {'REPORT.md':'\n'.join(out),'ALL-FAILURES.md':'\n'.join(fails)+'\n'}
if __name__=='__main__':
 for name,text in render().items():
  if (HERE/'result-manifest.json').exists():assert (HERE/name).read_text()==text
  else:(HERE/name).write_text(text)
