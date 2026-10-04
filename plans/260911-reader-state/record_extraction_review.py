"""Record the author's inspected decisions for all 52 captured event streams."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
assert not (HERE/'result-manifest.json').exists()
captures=json.loads((HERE/'run/extractions.json').read_text())
sources={s['id']:s for s in json.loads((HERE/'preflight/streams.json').read_text())}
assert len(captures)==52
# Explicit decisions from inspection of outputs, full histories and gold events.
wrong_owner={'S005','S010','S015','S020','S025','S030','S035','S040'}
polarity_value={'S003','S008','S042'}
wrong_property={'S044'}
omitted_other={'S045','S046','S051'}
invalid={'S049','S052'}
surface_only={'S001','S002','S004','S006','S007','S009'}
rows=[]
for c in captures:
    sid=c['id'];reason=[]
    semantic=quotes=state=True
    if sid in wrong_owner:
        semantic=quotes=state=False
        reason.append('The only relevant preference belongs to fictional Rowan/Vale, but the event labels its owner user and the resolver establishes a positive user preference. Exact substring anchoring cannot validate this owner assignment.')
        if sid in {'S005','S010'}:
            reason.append('The selected quote also drops the surrounding fictional-speaker framing, leaving a first-person sentence that cannot establish its owner by itself.')
    if sid in polarity_value:
        semantic=quotes=state=False
        if sid in {'S003','S008'}:
            reason.append('The later explicit negative uses operation set with the whole negative sentence as its value. The contract requires deny with the activity name. The resolved record consequently has positive polarity with a negated sentence as its value, violating the signed activity-value representation. The negative text remains visible, so a reader may recover the intended answer despite this state-contract failure.')
        else:
            reason.append('The event uses deny but places the whole phrase I do not enjoy trail running in value. The contract requires deny with value trail running. This encodes negation in both operator and value; it is not treated as a harmless positive-value surface expansion. The original negative sentence remains visible to the answer generator.')
    if sid in wrong_property:
        semantic=quotes=state=False
        reason.append('The T2 withdrawal concerns breakfast and explicitly retains writing-tool preference. Labeling it as a target-property withdrawal incorrectly clears the user\'s fountain-pen preference. The full exact quote exposes the relevance error; the resolver itself applies the supplied event as designed.')
    if sid in omitted_other:
        semantic=False
        reason.append('The emitted user events and their quotes are correct, but the sequence omits the relevant other-owner assertion. The extraction contract requires retaining such events with owner other. This omission leaves the computed current user state correct in this case; event completeness and state correctness therefore receive different scores.')
    if sid in invalid:
        semantic=quotes=state=False
        if sid=='S049':
            reason.append('The model adds a T2 denial with value MAY-ree although that value does not occur in its T2 evidence quote. The source describes the version anaphorically, but the frozen schema requires the value to be copied from the exact cited quote. The whole extraction is rejected, discarding the otherwise correct T0 MAH-ree event and producing an incorrect unknown fallback. This is a source-binding/schema limitation, not proof that the model failed to understand the user\'s intended pronunciation.')
        else:
            reason.append('The model uses a dictionary instead of the required five-field array and supplies a sentence instead of null for no_preference. The whole extraction is rejected. Unknown is the wrong fallback because the source explicitly establishes the absence of a dessert preference. The intended no_preference operation is visible in malformed output; format failure is distinguished from a claim that the source was misunderstood.')
    if sid in surface_only:
        reason.append('The model copies a full affirmative I enjoy sentence/phrase as a value instead of the required minimal activity name. This fails exact categorical matching and the minimal-value convention, but preserves the positive preference meaning, owner, chronology and quoted evidence. It is counted as semantically correct with a disclosed surface/schema deviation; no captured value is repaired. Where withdrawal follows, the current unknown record is exact.')
    if not reason:
        reason.append('All relevant user and other-owner events match the reviewed source semantics and order. Their exact quotes support owner, operation and value; the resulting current user state matches the reference.')
    evidence=[{'where':'answer','index':0,'quote':c['text']},
              {'where':'reader_message','index':1,'quote':c['messages'][1]['content']}]
    evidence.extend({'where':'history','index':i,'quote':m['content']} for i,m in enumerate(sources[sid]['history']))
    rows.append({'id':sid,'schema_and_spans_valid':c['parsed']['valid'],'semantic_events_correct':semantic,
                 'quotes_sufficient':quotes,'resolved_state_correct':state,'reason':' '.join(reason),'evidence':evidence})
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
review={'status':'complete','reviewer':'Codex, experiment author','model_version':'GPT-6',
    'reviewed_at':datetime.now(timezone.utc).isoformat(),
    'process_notes':'Unblinded author inspection of all 52 completed extraction outputs while the unchanged answer run continued. Final extraction bytes must match that inspected snapshot. Judgments separate exact categorical matching, semantically preserved positive value surface expansions, wrong owner/property, polarity-value contract violations, incomplete other-owner history, and whole-parse rejection. Semantic state correctness includes signed value interpretation; positive redundant phrasing is allowed, whereas mismatched or double-encoded negation is a state-contract failure. No runtime output or resolved state is repaired. Exact quote location does not establish semantic support. Historical answer controls bypass extraction.',
    'extractions_sha256':sha(HERE/'run/extractions.json'),'gold_events_sha256':sha(HERE/'preflight/gold-events.json'),
    'streams':rows,'training_labels':0}
(HERE/'extraction-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({field:sum(r[field] for r in rows) for field in ('schema_and_spans_valid','semantic_events_correct','quotes_sufficient','resolved_state_correct')}))
