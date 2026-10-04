from experiments.context_policy.corpus import audit_blueprints, build_blueprints, realization_messages


def test_blueprint_split_isolation_and_realizer_never_sees_questions():
    rows = build_blueprints()
    audit = audit_blueprints(rows)
    assert audit['families'] == 400 and audit['questions'] == 2000
    first = rows[0]
    before = realization_messages(first, first['sessions'][0])
    first['questions'] = [{'question': 'SECRET_TEST_QUESTION', 'answer': 'SECRET_GOLD', 'support': ['private']}]
    assert before == realization_messages(first, first['sessions'][0])
    assert 'SECRET' not in str(before)


def test_blueprints_are_reproducible_and_private_question_ids_are_unique():
    first, second = build_blueprints(), build_blueprints()
    assert first == second
    assert len({q['id'] for row in first for q in row['questions']}) == 2000
    assert {q['kind'] for row in first for q in row['questions']} == {
        'rejected_proposal', 'partial_correction', 'near_entities', 'multi_session',
        'old_instruction', 'abstention', 'routine_detail'}
