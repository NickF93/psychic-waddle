"""Rendered-answer visibility for the portfolio's safe Markdown contract."""

from markdown_it import MarkdownIt

# Match the widget's markdown-it default preset and enabled syntax exactly.
_MARKDOWN = MarkdownIt(
    "js-default", {"html": False, "breaks": True, "linkify": False}
).disable("image")
_TEXT_TOKENS = frozenset(("text", "code_inline", "code_block", "fence"))
# ECMAScript String.trim(), as used on the widget's rendered textContent.
_BROWSER_WHITESPACE = (
    "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007"
    "\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)


def has_visible_answer_text(markdown: str) -> bool:
    """Ignore Markdown structure and metadata, retaining literal visible text."""
    def contains_text(tokens):
        return any(
            contains_text(token.children)
            if token.children
            else token.type in _TEXT_TOKENS
            and bool(token.content.strip(_BROWSER_WHITESPACE))
            for token in tokens
        )

    return contains_text(_MARKDOWN.parse(markdown))
