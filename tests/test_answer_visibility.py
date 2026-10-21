"""Parity cases for the widget's rendered textContent.trim() contract."""

import pytest

from portfolio_rag_assistant.answer.visibility import has_visible_answer_text


@pytest.mark.parametrize(
    "text",
    (
        "", " \n\t", "- ", "*", "+ ", "1. ", "# ", "> ", "---",
        "```", "```python\n", "~~~python\n", "[ref]: https://example.test",
        "[ ](https://example.test)", "&#32;", "&nbsp;", "\ufeff",
    ),
)
def test_structure_and_whitespace_are_not_answer_text(text):
    assert not has_visible_answer_text(text)


@pytest.mark.parametrize(
    "text",
    (
        "Answer", "- Answer", "# Answer", "> Answer", "1. Answer",
        "```python\nprint(1)", "    print(1)", "**", "\\*", "`code`",
        "[Answer](https://example.test)", "![alt](https://example.test/image)",
        "<script>literal HTML</script>", "&amp;", "&#x85;", "&zwnj;",
    ),
)
def test_rendered_text_and_literal_punctuation_are_visible(text):
    assert has_visible_answer_text(text)
