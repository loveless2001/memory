"""Render source-bound descriptive diagnostic report and complete failure inventory."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
read=lambda n:json.loads((HERE/n).read_text())
ARMS=['direct','extracted_fact','oracle_fact','oracle_query']
def render():
 s=read('summary.json');r=read('review.json');cases=read('preflight/cases.json');cm={c['id']:c for c in cases};am={(a['arm'],a['id']):a for a in r['answers']};status=read('run/status.json');bill=read('billing.json');launch=read('run/launch.json')
 lines=['# Fact identification versus answer selection: frozen 4B diagnostic','',
 'The original pronunciation and dessert errors are repaired by independently extracting a fact record and then answering from it. This is useful evidence for a staged reader, but not a complete fix: extraction loses negative-preference state, and selection still turns unknown into a categorical No even with correct facts and an explicit question interpretation. No additional training occurred.','',
 'This is a descriptive, unblinded author-reviewed challenge set: sixteen short histories, four related questions each, four answer arms. Four histories are reused (twelve exact prior questions plus four added controls); twelve histories and 48 questions are new. The 64 correlated questions are not 64 independent trials or a random benchmark.','',
 '## Matched answer results','',
 'Strict correctness requires all seven frozen criteria: task completion, source consistency, visible support, withdrawal compliance, ownership, valid body and <=90 words. Required-answer correctness checks the requested answer separately from explanation support.','',
 '| Condition | Strict, all 64 | Required, all 64 | Strict, 16 reused-history questions | Strict, 48 new questions |','|---|---:|---:|---:|---:|']
 for a in ARMS:
  z=s['scores']['all'][a];lines.append(f"| {a} | {z['strict_correct']}/64 | {z['required_answer_correct']}/64 | {s['scores']['split:reused_history'][a]['strict_correct']}/16 | {s['scores']['split:new'][a]['strict_correct']}/48 |")
 lines+=['','Direct uses the original complete archive and answer prompt. Extracted fact uses a model-produced record and a different, fixed selection prompt. Oracle fact replaces that record with a reviewed correct record under the same selection prompt. Oracle query additionally supplies a reviewed operation/candidate interpretation. These oracle inputs are intentional privileges; no final answer reference or prior output was mounted.','',
 '## What the interventions reveal','',
 '- **N09-1, pronunciation:** direct says `Yes. You supplied MAH-ree.` when asked about MAY-ree. The independent extraction correctly records MAH-ree; all three record arms correctly answer No. N09-2 and both added question controls stay correct.',
 '- **N12-2, dessert:** direct says only `You have not specified a preferred dessert.` Extraction correctly records explicit none, and all record arms say the user has no preferred dessert. The other three forms stay correct.',
 '- **Candidate comparison:** the same direct wrong-Yes/right-value error occurs for Ravn/Raven, Soren/Sorren, and Vesta/Pallas. All record arms fix them. Vesta/Pallas are distant strings and the archive contains no assistant value substitution, so this is not confined to near spellings or conflicting assistant values. nah-LO/nah-RO and silver/orange work even directly.',
 '- **Known none:** besides dessert, direct omits explicit none for the open soup and bath-towel questions. The pen-cap binary answer has the correct No but falsely calls the preference unknown. All record arms fix these. Other question forms on those same histories work directly.',
 '- **Fact extraction:** all three negative-preference histories become status none. For velvet, the extracted quote also drops the explicit negative; three downstream answers regress. For laces and Marble, the quote retains the negative, and generated answers recover all eight requested answers from that quote despite the wrong status. Successful downstream prose therefore does not certify the typed record.',
 '- **Selection with correct facts:** both new withdrawal histories have correct unknown records. Extracted-fact and oracle-fact answers still give categorical No on the alternative-candidate questions X11-2 and X12-2. Oracle query fixes none of these and introduces No on X11-1 and X12-1 as well. More explicit question information is not sufficient.',
 '',
 'Changing to record prompts also changes formatting, instructions and available evidence, so these behavioral interventions do not prove that the direct model internally implements separate extraction and selection stages. The experiment localizes failures in this constructed pipeline. It does not admit deployment or retrieval-policy training.','',
 '## Extraction and record faithfulness','',
 '| Check | Histories passing |','|---|---:|']
 for k,label in [('schema_and_spans_valid','Schema and exact user-span checks'),('raw_semantic_meaning_correct','Source-reviewed semantic meaning'),('usable_correct_record','Usable semantically correct record'),('literal_record_matches_gold','Literal status/value match to gold'),('evidence_sufficient_for_true_state','Quote sufficient for the true state'),('ownership_correct','Correct user ownership')]:lines.append(f"| {label} | {s['extraction'][k]}/16 |")
 lines+=['',
 'The semantic score accepts `silver` as a sufficient contextual value for the parcel pickup counter, since the property and exact quote say silver counter. The frozen literal selector does not equate those strings. This is one representation mismatch, separate from the three negative-to-none semantic errors. No alias mapping was added after inference.','',
 'With semantically correct records, generated selection passes 50/52 questions and fails the two withdrawal binaries. With incorrect records, it passes 9/12: one velvet candidate answer is correct despite lost state, and eight laces/Marble answers recover from the retained negative quotes. There are no invalid-record fallbacks to credit. Record-prompt faithfulness is 62/64 for extracted fact, 62/64 for oracle fact and 60/64 for oracle query; correctness relative to the original source is a separate criterion. In extracted fact, only 54/64 answers follow the typed status: eight source-correct answers instead use quotes contradicting that status.','',
 '| Stream | Gold state/value | Generated state/value | Semantic correctness | Literal match |','|---|---|---|---|']
 for x in r['extractions']:
  g=x['evidence']['gold'];v=x['evidence']['parsed']['record'];lines.append(f"| {x['id']} | {g['status']}: {g['value']} | {v['status']}: {v['value']} | {x['record_state_correct']} | {x['literal_record_matches_gold']} |")
 lines+=['','## Deterministic selector with oracle query parsing','',
 f"Gold record plus reviewed query interpretation gives 64/64 by construction. Model record plus the same oracle query interpretation gives **{s['mechanical_selector']['model_record_correct']}/64**. This is not a learned or autonomous query parser. It uses only case-folded literal comparisons and does not reason over the quote.",'',
 'The twelve failures comprise three per negative history (the stated-negative question and two lookups) and three on the silver abbreviation (positive candidate plus two lookups). Generated prose recovers from context/quotes where the literal selector cannot, but the literal selector preserves unknown correctly. This exposes a tradeoff between robust representations and flexible interpretation; neither component is solved by this result.','',
 '## Matched corrections and regressions','']
 for pair,metrics in s['matched_transitions'].items():
  for metric,z in metrics.items():lines.append(f"- {pair}, {metric}: corrected {', '.join(z['corrected']) or 'none'}; regressed {', '.join(z['regressed']) or 'none'}.")
 lines+=['','## Breakdown by fact type and question form','', '| Group | Questions | Direct strict | Extracted strict | Oracle fact strict | Oracle query strict |','|---|---:|---:|---:|---:|---:|']
 for name,arms in s['scores'].items():
  if name.startswith(('kind:','question_form:')):lines.append('| '+name+' | '+str(arms['direct']['total'])+' | '+' | '.join(str(arms[a]['strict_correct']) for a in ARMS)+' |')
 lines+=['','For each history, all four related answers are strictly correct on '+', '.join(f"{a}: {len(s['history_consistency'][a]['fully_strict_correct_histories'])}/16" for a in ARMS)+'. These counts describe consistency across question forms, not independent replicated trials.','',
 '## Wording sensitivity and review limits','',
 'The frozen primary rule counts a categorical `No.` after withdrawal as a negative assignment, even when followed by an unknown clause. `No evidence supports ...` is instead an epistemic statement and passes. If every categorical-No failure were read generously as refusal to assert a candidate, strict scores would be direct 56/64, extracted 61/64, oracle fact 64/64 and oracle query 64/64. Primary scores remain unchanged. X12-1 in oracle query also says no preference was explicitly stated, which can be read historically and is unsupported on that reading; the generous score assumes a current-evidence reading.','',
 'Candidate-scoped “no preference for laces” is accepted as denying preference for laces when the source quote states that negative; it is not accepted as evidence of global none. “Not specified a preference” alone on an explicit-none lookup is incomplete, following the retained N12-2 rule. Full source, actual prompt, response and decision are recorded for every answer. Review was unblinded and performed by the experiment author, not an independent judge.','',
 '## Execution, provenance and accounting','',
 f"App [{launch['app_id']}](https://modal.com/apps/syntracts/main/{launch['app_id']}) completed in {status['elapsed_seconds']:.3f} function seconds; stopped with zero tasks. One H100, zero retries, hard timeout 1,200 seconds. Observed billing: **${bill['reported_total_usd']}**, snapshot {bill['observed_at']} (billing may lag).",'',
 'All 256 answers and 16 extractions completed. All answers satisfy body and word limits. All 25 cached/fresh checks pass, including initial argmax and up to sixteen generated tokens. All twelve prior direct prompts, token sequences and texts reproduce exactly. Complete base and adapter tensor hashes are identical before/after, all parameters frozen, zero optimizer steps/labels, and all 1,390 protected files unchanged.','',
 '| Calls | Count | Input tokens | Generated tokens | Forwarded tokens | Generation seconds |','|---|---:|---:|---:|---:|---:|']
 for a,z in s['verification']['accounting_by_arm'].items():lines.append(f"| {a} | {z['calls']} | {z['input_tokens']} | {z['generated_tokens']} | {z['forwarded_tokens']} | {z['generation_seconds']:.3f} |")
 e=s['verification']['accounting_by_arm']['extract'];a=s['verification']['accounting_by_arm']['extracted_fact']
 lines+=['',f"Including the sixteen one-time extractions amortized across four queries each, extracted-fact input tokens total {e['input_tokens']+a['input_tokens']}, generated tokens {e['generated_tokens']+a['generated_tokens']}, forwarded tokens {e['forwarded_tokens']+a['forwarded_tokens']}, and summed generation time {e['generation_seconds']+a['generation_seconds']:.3f}s. This is not an end-to-end latency benchmark or a serving cost result. Gates, loading, commits and verification add overhead; gate accounting is separately retained in summary.json. Oracle authoring costs are not included.",'',
 'Artifacts: [frozen plan](preflight/PLAN.md), [all failures](ALL-FAILURES.md), [complete review](review.json), [explicit author decisions](review-decisions.json), [summary](summary.json), [artifact verification](run/artifact-verification.json). Reproduce local verification with `.venv/bin/python plans/260911-reader-factor/verify_results.py`. No follow-up run was launched.','']
 failures=['# All answer failures and extraction deviations','','Strict failures only; full passing and failing evidence is in review.json.']
 for j in r['answers']:
  if j['verdict']=='pass':continue
  c=cm[j['id']];failures+=['',f"## {j['arm']} / {j['id']}",'',f"Question: {c['query']}",'',f"Answer: {j['evidence']['answer']}",'',f"Reference: {c['reference']['answer']}",'','Failed criteria: '+', '.join(k for k in ('task_complete','source_consistent','supported_in_visible_state','withdrawal_compliant','ownership_correct','body_valid','within_90_words') if not j[k])+'.','',j['reason'],'','Source:']
  failures += [f"- T{i} {m['role']}: {m['content']}" for i,m in enumerate(c['history'])]
  if j['arm']!='direct':failures+=['','Actual record/query message:','```',j['evidence']['actual_messages'][1]['content'],'```']
 failures+=['','## Extraction deviations','']
 for x in r['extractions']:
  if x['literal_record_matches_gold']:continue
  failures+=[f"### {x['id']}",'',x['reason'],'','Generated: `'+x['evidence']['raw']+'`','', 'Gold: `'+json.dumps(x['evidence']['gold'],ensure_ascii=False)+'`','']
 return {'REPORT.md':'\n'.join(lines),'ALL-FAILURES.md':'\n'.join(failures)+'\n'}
if __name__=='__main__':
 for name,text in render().items():
  if (HERE/'result-manifest.json').exists():assert (HERE/name).read_text()==text
  else:(HERE/name).write_text(text)
