from paper_research_copilot.agent import QuestionAmbiguityGate


def test_question_gate_rejects_unresolved_reference() -> None:
    result = QuestionAmbiguityGate().screen("请详细解释刚才提到的那篇论文。")

    assert result.decision == "ambiguous"
    assert result.rule_id == "unresolved_reference"


def test_question_gate_rejects_unscoped_superlative() -> None:
    result = QuestionAmbiguityGate().screen("目前最好的 Agent Memory 方法是什么？")

    assert result.decision == "ambiguous"
    assert result.rule_id == "unscoped_superlative"


def test_question_gate_rejects_underspecified_selection() -> None:
    result = QuestionAmbiguityGate().screen("我应该使用哪篇 Agent 论文里的方法？")

    assert result.decision == "ambiguous"
    assert result.rule_id == "underspecified_selection"


def test_question_gate_allows_concrete_mechanism_question() -> None:
    result = QuestionAmbiguityGate().screen(
        "哪种方法通过 Thought、Action、Observation 交替使用外部工具？"
    )

    assert result.decision == "clear"
    assert result.rule_id is None
