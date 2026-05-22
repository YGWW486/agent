"""P1 — ReviewResult 契约测试"""
from agent.models import human_reject_review, review_from_json, review_to_json


def test_human_reject_review_valid():
    rev = human_reject_review("需要补充单元测试")
    assert rev.verdict == "REJECT"
    assert rev.source == "human"
    assert len(rev.test_cases) >= 1
    assert "人工审查拒绝" in rev.reason


def test_human_reject_roundtrip_json():
    raw = review_to_json(human_reject_review("comment"))
    parsed = review_from_json(raw)
    assert parsed.source == "human"
    assert parsed.test_cases[0].name == "manual_reject_placeholder"
