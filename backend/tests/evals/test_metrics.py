from decimal import Decimal

import pytest

from evals.metrics import (
    bootstrap_ci,
    cohen_kappa,
    has_order_by,
    mcnemar,
    paired_bootstrap_diff,
    percentile,
    prf,
    results_equal,
    results_equal_relaxed,
)


def test_results_equal_multiset_and_tolerance() -> None:
    gold = [("Алматы", Decimal("1500.5000001")), ("Астана", 10)]
    assert results_equal(gold, [("Астана", 10.0), ("Алматы", 1500.5)], ordered=False)
    assert not results_equal(gold, [("Астана", 10.0), ("Алматы", 1500.5)], ordered=True)
    assert not results_equal(gold, [("Алматы", 1500.6), ("Астана", 10)], ordered=False)
    # дубликаты важны: мультимножество, а не множество
    assert not results_equal([(1,), (1,)], [(1,), (2,)], ordered=False)
    assert results_equal([], [], ordered=False)
    assert not results_equal([(1,)], [], ordered=False)


def test_results_equal_column_permutation() -> None:
    assert results_equal([("a", 1), ("b", 2)], [(2, "b"), (1, "a")], ordered=False)
    assert not results_equal([("a", 1)], [("a", 1, 3)], ordered=False)


def test_results_equal_normalizes_text_numbers() -> None:
    assert results_equal([("12.50",)], [(12.5,)], ordered=False)
    assert results_equal([(True,)], [(1,)], ordered=False)


def test_relaxed_allows_extra_columns() -> None:
    gold = [("defect", 100), ("late_delivery", 50)]
    pred = [("defect", 7, 100), ("late_delivery", 3, 50)]
    assert not results_equal(gold, pred, ordered=False)
    assert results_equal_relaxed(gold, pred, ordered=False)
    assert not results_equal_relaxed(gold, [("defect", 7, 99), ("x", 3, 50)], ordered=False)


def test_has_order_by() -> None:
    assert has_order_by("SELECT a FROM t ORDER BY a DESC LIMIT 5")
    assert not has_order_by("SELECT a FROM (SELECT a FROM t ORDER BY a) s")
    assert not has_order_by("SELECT count(*) FROM t")


def test_mcnemar_exact() -> None:
    a = [True] * 10 + [False] * 10
    b = [True] * 10 + [True] * 10  # B исправила 10 ошибок A, ничего не сломала
    r = mcnemar(a, b)
    assert (r["b01"], r["b10"]) == (10, 0)
    assert r["p_value"] == pytest.approx(2 / 2**10, abs=1e-4)
    assert mcnemar(a, a)["p_value"] == 1.0


def test_bootstrap_intervals() -> None:
    values = [1.0] * 70 + [0.0] * 30
    lo, hi = bootstrap_ci(values)
    assert lo < 0.7 < hi and hi - lo < 0.25
    assert bootstrap_ci([]) == (0.0, 0.0)
    lo, hi = paired_bootstrap_diff([0.0] * 50 + [1.0] * 50, [1.0] * 100)
    assert 0.35 < lo < 0.5 <= hi < 0.65


def test_prf_kappa_percentile() -> None:
    assert prf(8, 2, 2) == {"precision": 0.8, "recall": 0.8, "f1": 0.8}
    assert prf(0, 0, 5)["recall"] == 0.0
    # классический пример: 20 из 25 совпадений при равных маргиналах
    a = ["yes"] * 15 + ["no"] * 10
    b = ["yes"] * 12 + ["no"] * 3 + ["yes"] * 3 + ["no"] * 7
    assert cohen_kappa(a, b) == pytest.approx(0.5, abs=0.01)
    assert cohen_kappa(["x", "x"], ["x", "x"]) == 1.0
    assert percentile([1, 2, 3, 4], 0.5) == 2.5


def test_gold_tables() -> None:
    from evals.metrics import gold_tables

    sql = (
        "WITH t AS (SELECT * FROM orders) SELECT r.name FROM t "
        "JOIN customers c ON c.id = t.customer_id JOIN regions r ON true"
    )
    assert gold_tables(sql) == {"orders", "customers", "regions"}
