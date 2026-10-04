"""Apply user-approved rubric rulings as a separately attributed author overlay."""
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKET = HERE.with_name('20260911-v2-broader-answer-review')
AUDIT = HERE.with_name('20260911-v2-broader-review-audit')
FIELDS = ('task_complete', 'source_consistent', 'supported_in_visible_state',
          'withdrawal_compliant', 'ownership_correct', 'body_valid', 'within_90_words')
THIRTEEN = {
    'C024-B': 'Calls the preference withdrawn and connects the current negative record to that account.',
    'C036-C': 'Presents the detail as withdrawn and no longer to be considered.',
    'C037-A': 'Cites T82 withdrawal and claims the system has acknowledged and forgotten the detail.',
    'C037-B': 'Explains the negative by describing the preference as withdrawn in the record.',
    'C037-C': 'Cites T82 withdrawal and says the system has since forgotten the detail.',
    'C045-A': 'Adds that the withdrawn preference is no longer factored into future responses.',
    'C045-B': 'Adds that the withdrawn preference is no longer considered current.',
    'C045-C': 'Follows the negative with withdrawal of this preference in the user history.',
    'C050-A': 'Cites T274 withdrawal and says the preference is no longer considered in future responses.',
    'C050-C': 'Cites T274 withdrawal and says it is no longer part of current details.',
    'C076-A': 'Cites T189 withdrawal and says the system has since forgotten the preference.',
    'C076-B': 'Cites T189 withdrawal and describes it as confirmed in subsequent interactions.',
    'C084-B': 'Cites T222 withdrawal and says it has been consistently acknowledged subsequently.',
}


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x): return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def write(p, x): p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')


def main():
    if (HERE / 'freeze.json').exists(): raise RuntimeError('Frozen adjudication; use verify.py')
    parent = read(HERE / 'claude-corrected-review.json')
    merged = copy.deepcopy(parent)
    old = {a['answer_id']: a for c in parent['cases'] for a in c['answers']}
    actual = {}
    for row in read(PACKET / 'packet/index.json'):
        c = read(PACKET / 'packet' / row['file'])
        for a in c['answers']: actual[a['answer_id']] = (c, a)
    decisions = []
    support_ids = list(THIRTEEN) + ['C020-B', 'C020-C', 'C026-A', 'C069-A', 'C069-B', 'C079-B']
    for aid in support_ids:
        case, answer = actual[aid]; history = read(PACKET / 'packet' / case['history_file'])['turns']
        replacement = copy.deepcopy(old[aid])
        assert replacement['source_consistent'] is False and replacement['supported_in_visible_state'] is True
        evidence = [{'where': 'answer', 'index': 0, 'quote': answer['text']}]
        turns = sorted({e['turn'] for row in case['reviewed_reference']['constraints'] +
                        case['reviewed_reference']['personal_claims'] for e in row['evidence']})
        for turn in turns:
            text = history[turn]['content']
            evidence.append({'where': 'history', 'index': turn, 'quote': text})
            # Exact visible quotations, including escaped text inside the JSON archive wrapper.
            visible = []
            for i, msg in enumerate(answer['actual_messages']):
                for candidate in (text, json.dumps(text, ensure_ascii=False)[1:-1]):
                    if candidate in msg['content']:
                        visible.append({'where': 'reader_message', 'index': i, 'quote': candidate})
                        break
            if aid in THIRTEEN:
                assert visible, (aid, turn, 'required later/withdrawal statement not fully visible')
            evidence += visible[:1]
        if aid in THIRTEEN:
            reason = (THIRTEEN[aid] + ' Both the older withdrawal and the later explicit negative are visible in full. '
                'This overlay retains the correction reviewer\'s interpretation of the withdrawal sentence as an invalid '
                'explanation of the current negative, rather than two independent supported statements. Under that '
                'retained interpretation, whole-answer support is false despite support for the final value. This is '
                'an interpretive ruling, not proof of the model\'s internal reasoning or a penalty for missing a citation.')
            kind = 'whole_answer_support_retaining_explanation_finding'
        elif aid.startswith('C020-'):
            replacement['task_complete'] = True
            reason = ('The answer supplies autumn and safety as the requested season and focus. T0 itself also mentions '
                'a warm, comforting atmosphere, so these concepts are not assistant-only and task_complete is true. '
                'The retained source-consistency failure is narrowed to the added assurance about guests being embraced '
                'or cared for from the moment they enter, which the original post does not establish. Visible assistant '
                'wording does not support attributing that assurance to the original user passage; whole-answer support is false.')
            kind = 'restore_task_completeness_and_apply_source_scope_to_support'
        elif aid == 'C026-A':
            reason = ('Retain the correction reviewer\'s rejection of the withdrawal explanation: the current negative '
                'is supported by the later statement, but the explanation treats this preference as withdrawn. '
                'Whole-answer support must include that explanation, consistently with the thirteen related cases. '
                'No claim about hidden model reasoning is made.')
            kind = 'same_explanation_support_rule'
        else:
            reason = ('The final value is supported, but the answer asserts a chronology contradicted by the visible '
                'turn order. Retain task completeness and the existing source/withdrawal failure, and set whole-answer '
                'support false. Availability of the correct dates does not entail the reversed chronology asserted.')
            kind = 'false_chronology_is_not_supported'
        replacement.update(supported_in_visible_state=False, reason=reason, evidence=evidence)
        decisions.append({'answer_id': aid, 'decision': 'replace', 'kind': kind,
            'parent_judgment_sha256': digest(old[aid]), 'changed_criteria': {
                f: {'before': old[aid][f], 'after': replacement[f]} for f in FIELDS if old[aid][f] != replacement[f]},
            'replacement': replacement})
    decisions.append({'answer_id': 'C073-B', 'decision': 'retain', 'kind': 'retain_frozen_question_ambiguity',
        'parent_judgment_sha256': digest(old['C073-B']), 'changed_criteria': {}, 'replacement': None,
        'reason': 'The question does not unambiguously request the university name. Preserve ambiguous; naming Temple in the reference cannot retroactively sharpen the query.'})
    replacements = {r['answer_id']: r['replacement'] for r in decisions if r['decision'] == 'replace'}
    for case in merged['cases']:
        case['answers'] = [replacements.get(a['answer_id'], a) for a in case['answers']]
    provenance = {'author': 'Codex (GPT-6), experiment author; user-approved adjudication',
        'authorization': 'User: ok go ahead, following the three stated rulings on support, C020 completeness and C073 ambiguity.',
        'scope': 'Whole-answer support, restored C020 task completeness, retained C073 ambiguity. No fresh independent review.',
        'parent_review_sha256': sha(HERE / 'claude-corrected-review.json'),
        'reviewer_explanation_interpretation_retained': True,
        'not_claimed': ['proof of hidden reasoning', 'independent author adjudication', 'training admission'],
        'decisions': decisions}
    write(HERE / 'adjudication.json', provenance)
    merged['reviewer'] += '; author adjudication by Codex (GPT-6), user-approved'
    merged['model_version'] += '; author adjudicator GPT-6'
    merged['reviewed_at'] = '2026-09-10T20:22:42+00:00'
    merged['blinding_notes'] += ' Final author overlay is unblinded and not independently re-reviewed.'
    merged['process_notes'] += ' User-approved whole-answer support ruling applied; C020 task completeness restored; C073 ambiguity retained. Explanation interpretations remain those of the correction reviewer.'
    merged['author_adjudication'] = {'file': 'adjudication.json', 'sha256': sha(HERE / 'adjudication.json'),
                                    'parent_review_sha256': provenance['parent_review_sha256']}
    write(HERE / 'adjudicated-review.json', merged)
    mapping = {c['case_id']: c for c in read(PACKET / 'sealed-map.json')}
    classes = {1:'historical_recall',2:'historical_recall',3:'withdrawal',4:'attribution',5:'different_value',6:'same_value'}
    counts = Counter(); criteria = {f:Counter() for f in FIELDS}; by_round = defaultdict(Counter)
    by_class = defaultdict(lambda: defaultdict(Counter)); pairs = {str(n):Counter() for n in (1,2)}
    for c in merged['cases']:
        m = mapping[c['case_id']]; am = {a['answer_id']:a['retrieval_rounds'] for a in m['answers']}
        kind = classes[int(m['original_id'].split('Q')[1])]; states = {}
        for a in c['answers']:
            n=am[a['answer_id']];v=a['verdict'];counts[v]+=1;by_round[str(n)][v]+=1;by_class[kind][str(n)][v]+=1;states[n]=v
            for f in FIELDS:criteria[f][str(a[f]).lower()]+=1
        if set(states)=={0,1,2}:
            for n in (1,2):pairs[str(n)][states[0]+' -> '+states[n]]+=1
    write(HERE / 'summary.json', {'verdicts':counts,'criteria':criteria,'by_retrieval':by_round,
        'by_frozen_class_and_retrieval':by_class,'paired_complete_questions':87,'transitions_from_zero':pairs,
        'adjudicated_answers':len(decisions),'support_true_to_false':len(support_ids),'task_false_to_true':2,
        'verdict_changes_from_claude_correction':0,'independent_review_of_author_overlay':False,'training_labels':0})
    print(json.dumps({'verdicts': counts, 'criteria': criteria}, indent=2))


if __name__ == '__main__': main()
