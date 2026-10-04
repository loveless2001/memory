"""Check frozen authoring, raw provenance, reader separation and audit bindings."""
import json
from pathlib import Path
from experiments.context_policy.personamem import reader_history, sha256
from experiments.context_policy.relabel import canonical, validate_reference
from experiments.context_policy.repair_pilot import validate_bundle

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def main():
    def read(name): return json.loads((OUT / name).read_text())
    def lines(name): return [json.loads(s) for s in (OUT / name).read_text().splitlines()]
    bundle = read('reader-input.json'); validate_bundle(bundle)
    records = lines('records.jsonl'); refs = lines('references.jsonl')
    packets = lines('audit-packets.jsonl')
    old = json.loads((ROOT / 'data/context-policy/personamem-v2/repair-v1/pilot-reader-input.json').read_text())
    assert bundle['histories'] == old['histories']
    assert len(records) == len(refs) == len(packets) == len(bundle['questions']) == 50
    assert not {x['id'] for x in bundle['questions']} & {x['id'] for x in old['questions']}
    assert not {x['query']['content'] for x in bundle['questions']} & {x['query']['content'] for x in old['questions']}
    for record, ref, packet, question in zip(records, refs, packets, bundle['questions']):
        validate_reference(record, ref)
        assert question == {k: record[k] for k in ('id', 'persona_id', 'query')}
        assert packet['id'] == record['id']
        assert record['history'] == bundle['histories'][record['persona_id']]
        raw = ROOT / 'data/context-policy/personamem-v2' / record['history_path']
        assert sha256(raw.read_bytes()) == record['source_sha256']
        assert reader_history(json.loads(raw.read_text())) == record['history']
        assert len(ref['answer'].split()) <= 90
    frozen = read('freeze.json')['files']
    previous = read('previous-artifact-hashes.json')
    for path, digest in {**previous, **frozen}.items():
        assert sha256((ROOT / path).read_bytes()) == digest, path
    contexts = {x['id']: x for x in read('contexts.json')}
    audits = {x['id']: x for x in read('availability.json')}
    reviews = read('semantic-review.json')
    assert len(contexts) == len(audits) == len(reviews) == 50
    for review in reviews:
        rid = review['id']
        assert review['availability_sha256'] == sha256(canonical(audits[rid]))
        assert review['context_sha256'] == sha256(canonical(contexts[rid]))
        assert review['action_target'] is None and review['reader_answer_reviewed'] is False
    result = dict(status='pass', source_record_checks=50, reference_validations=50,
                  original_source_groups=10, reader_schema='history/query only',
                  old_questions_disjoint=True, frozen_files_verified=len(frozen),
                  previous_files_unchanged=len(previous), semantic_review_bindings=50,
                  independent_review=False, training_exported=False, reader_generation=False,
                  output_hashes={p.name: sha256(p.read_bytes()) for p in sorted(OUT.iterdir())
                                 if p.is_file() and p.name != 'verification.json'})
    (OUT / 'verification.json').write_bytes(canonical(result))
    print(json.dumps({k: v for k, v in result.items() if k != 'output_hashes'}))


if __name__ == '__main__': main()
