import pytest
import torch

from memsub.compaction.attention_weighted_kv_merge import (
    build_merge_plan,
    mechanics_features,
    merge_cache,
)
from memsub.runtime import CompactedPrefixCache


@pytest.mark.parametrize(
    ("fraction", "retained"),
    [(0.25, 3072), (0.40, 2458), (0.90, 410)],
)
def test_merge_plan_exactly_matches_house_budget(fraction, retained):
    plan = build_merge_plan(4096, fraction)

    assert plan.target_retained == retained
    assert plan.sink_token_count + plan.summary_count + plan.recent_count == retained


@pytest.mark.parametrize("fraction", [0.25, 0.40, 0.90])
def test_merge_plan_blocks_exactly_partition_the_old_nonsink_region(fraction):
    plan = build_merge_plan(4096, fraction)

    assert plan.blocks[0].start == plan.sink_token_count
    assert plan.blocks[-1].end == plan.recent_start
    assert all(left.end == right.start for left, right in zip(plan.blocks, plan.blocks[1:]))
    assert sum(block.size for block in plan.blocks) == (
        plan.sequence_length - plan.sink_token_count - plan.recent_count
    )
    assert max(block.size for block in plan.blocks) - min(
        block.size for block in plan.blocks
    ) <= 1


def _scalar_cache(sequence_length=8, sink_token_count=2):
    positions = torch.arange(sequence_length, dtype=torch.float32)
    keys = [
        positions.view(1, 1, sequence_length, 1),
        (100 + positions).view(1, 1, sequence_length, 1),
    ]
    values = [10 * tensor for tensor in keys]
    return CompactedPrefixCache.from_tensors(
        keys,
        values,
        logical_positions=list(range(sequence_length)),
        next_logical_position=sequence_length,
        sink_token_count=sink_token_count,
    )


def test_merge_cache_uses_layer_and_kv_head_specific_attention_weights():
    cache = _scalar_cache()
    plan = build_merge_plan(8, 0.5, sink_token_count=2)
    mass = torch.zeros((2, 1, 8), dtype=torch.float32)
    mass[0, 0, 6] = 1
    mass[1, 0, 2] = 1

    result = merge_cache(cache, mass, plan)

    assert result.cache.physical_length == 4
    assert result.cache.logical_positions == [0, 1, 6, 7]
    assert result.cache.layer_kv(0)[0][0, 0, :, 0].tolist() == [0, 1, 6, 7]
    assert result.cache.layer_kv(0)[1][0, 0, :, 0].tolist() == [0, 10, 60, 70]
    assert result.cache.layer_kv(1)[0][0, 0, :, 0].tolist() == [
        100,
        101,
        102,
        107,
    ]


def test_merge_cache_uses_uniform_average_when_a_block_has_zero_attention_mass():
    cache = _scalar_cache()
    original_keys = [cache.layer_kv(i)[0].clone() for i in range(cache.num_layers)]
    plan = build_merge_plan(8, 0.5, sink_token_count=2)

    result = merge_cache(cache, torch.zeros((2, 1, 8)), plan)

    assert result.cache.layer_kv(0)[0][0, 0, :, 0].tolist() == [0, 1, 4, 7]
    assert result.cache.layer_kv(1)[0][0, 0, :, 0].tolist() == [
        100,
        101,
        104,
        107,
    ]
    for layer_index, original in enumerate(original_keys):
        assert torch.equal(cache.layer_kv(layer_index)[0], original)


def test_mechanics_features_describe_the_block_containing_the_needle_midpoint():
    plan = build_merge_plan(12, 0.5, sink_token_count=2)
    mass = torch.zeros((1, 1, 12), dtype=torch.float32)
    mass[0, 0, 2] = 1
    mass[0, 0, 3] = 3

    features = mechanics_features(plan, mass, needle_positions=[3])

    expected_heterogeneity = 1 - (
        -(0.25 * torch.log(torch.tensor(0.25)) + 0.75 * torch.log(torch.tensor(0.75)))
        / torch.log(torch.tensor(4.0))
    )
    assert features.merged is True
    assert features.block_size == 4
    assert features.attention_mass_share == pytest.approx(0.75)
    assert features.block_heterogeneity == pytest.approx(float(expected_heterogeneity))
    assert features.distance_to_recent_window == pytest.approx(0.5)


def test_mechanics_features_mark_a_needle_in_the_recent_window_as_exact():
    plan = build_merge_plan(12, 0.5, sink_token_count=2)

    features = mechanics_features(
        plan,
        torch.ones((1, 1, 12), dtype=torch.float32),
        needle_positions=[10],
    )

    assert features.merged is False
    assert features.block_size == 1
    assert features.attention_mass_share == 1.0
    assert features.block_heterogeneity == 0.0
    assert features.distance_to_recent_window == 0.0


@pytest.mark.parametrize("invalid_mass", [-1.0, float("nan"), float("inf")])
def test_merge_cache_rejects_nonfinite_or_negative_attention_mass(invalid_mass):
    cache = _scalar_cache()
    plan = build_merge_plan(8, 0.5, sink_token_count=2)
    mass = torch.ones((2, 1, 8), dtype=torch.float32)
    mass[0, 0, 3] = invalid_mass

    with pytest.raises(ValueError, match="finite and nonnegative"):
        merge_cache(cache, mass, plan)


def test_merge_api_is_available_from_compaction_package():
    from memsub.compaction import (
        MergeBlock,
        MergeMechanics,
        MergePlan,
        MergeResult,
        build_merge_plan as public_build_merge_plan,
        mechanics_features as public_mechanics_features,
        merge_cache as public_merge_cache,
    )

    assert MergeBlock is not None
    assert MergePlan is not None
    assert MergeMechanics is not None
    assert MergeResult is not None
    assert public_build_merge_plan is build_merge_plan
    assert public_merge_cache is merge_cache
    assert public_mechanics_features is mechanics_features
