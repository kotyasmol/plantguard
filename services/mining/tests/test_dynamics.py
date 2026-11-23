from plantguard_mining import Evidence, OverallTrend, calculate_dynamics


def evidence(code: str, confidence: float) -> Evidence:
    return Evidence(code=code, confidence=confidence, source="test")


def test_worsening_when_new_finding_appears():
    result = calculate_dynamics((), (evidence("leaf-yellowing", 0.82),))

    assert result.trend is OverallTrend.WORSENING
    assert result.changes[0].direction.value == "appeared"


def test_improving_when_finding_resolves():
    result = calculate_dynamics((evidence("leaf-dark-spots", 0.88),), ())

    assert result.trend is OverallTrend.IMPROVING
    assert result.changes[0].direction.value == "resolved"


def test_opposing_changes_produce_mixed_trend():
    result = calculate_dynamics(
        (
            evidence("leaf-yellowing", 0.90),
            evidence("leaf-dark-spots", 0.66),
        ),
        (
            evidence("leaf-yellowing", 0.60),
            evidence("leaf-dark-spots", 0.88),
        ),
    )

    assert result.trend is OverallTrend.MIXED
    assert {change.direction.value for change in result.changes} == {
        "resolved",
        "increased",
    }


def test_weak_findings_do_not_create_false_change():
    result = calculate_dynamics(
        (evidence("leaf-yellowing", 0.40),),
        (evidence("leaf-yellowing", 0.55),),
    )

    assert result.trend is OverallTrend.UNDETERMINED
    assert result.changes == ()
