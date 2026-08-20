from paper_research_copilot.agent import (
    QuestionAmbiguityGate,
    build_clarified_question,
    clarification_for,
)


def test_question_gate_rejects_unresolved_reference() -> None:
    result = QuestionAmbiguityGate().screen("请详细解释刚才提到的那篇论文。")

    assert result.decision == "ambiguous"
    assert result.rule_id == "unresolved_reference"
    clarification = clarification_for(result)
    assert clarification is not None
    assert clarification.required_information == (
        "论文标题、作者、arXiv ID 或明确的方法名称",
    )


def test_question_gate_rejects_truncated_deictic_reference() -> None:
    result = QuestionAmbiguityGate().screen("请详细解释刚才提到的那篇论")

    assert result.decision == "ambiguous"
    assert result.rule_id == "unresolved_reference"


def test_question_gate_rejects_deictic_reference_without_object_name() -> None:
    result = QuestionAmbiguityGate().screen("刚刚介绍的那个具体是如何训练的？")

    assert result.decision == "ambiguous"
    assert result.rule_id == "unresolved_reference"


def test_question_gate_rejects_unscoped_superlative() -> None:
    result = QuestionAmbiguityGate().screen("目前最好的 Agent Memory 方法是什么？")

    assert result.decision == "ambiguous"
    assert result.rule_id == "unscoped_superlative"
    clarification = clarification_for(result)
    assert clarification is not None
    assert len(clarification.required_information) == 2


def test_question_gate_rejects_underspecified_selection() -> None:
    result = QuestionAmbiguityGate().screen("我应该使用哪篇 Agent 论文里的方法？")

    assert result.decision == "ambiguous"
    assert result.rule_id == "underspecified_selection"
    clarification = clarification_for(result)
    assert clarification is not None
    assert "关键约束" in clarification.required_information[1]


def test_question_gate_allows_concrete_mechanism_question() -> None:
    result = QuestionAmbiguityGate().screen(
        "哪种方法通过 Thought、Action、Observation 交替使用外部工具？"
    )

    assert result.decision == "clear"
    assert result.rule_id is None
    assert clarification_for(result) is None


def test_question_gate_accepts_a_specific_clarification() -> None:
    question = build_clarified_question(
        "请详细解释刚才提到的那篇论文。",
        "ReAct: Synergizing Reasoning and Acting in Language Models",
    )

    result = QuestionAmbiguityGate().screen(question)

    assert result.decision == "clear"


def test_question_gate_requests_clarification_again_for_generic_reference() -> None:
    question = build_clarified_question(
        "请详细解释刚才提到的那篇论文。",
        "这篇论文",
    )

    result = QuestionAmbiguityGate().screen(question)

    assert result.decision == "ambiguous"
    assert result.rule_id == "unresolved_reference"
