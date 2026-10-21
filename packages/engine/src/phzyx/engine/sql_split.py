"""Split a SQL script the way PostgreSQL's lexer does.

``migrate_apply`` runs one statement per driver call. Splitting on every
``;`` cuts function bodies, string literals, and quoted identifiers.
"""

from __future__ import annotations


def split_statements(script: str) -> list[str]:
    """Return the statements in ``script``, in order.

    A semicolon ends a statement only outside a quoted string, a quoted
    identifier, a dollar-quoted body, or a comment. Comments that sit
    inside a statement are kept, because the slice is the original text.
    A file that is only comments yields nothing. An unterminated quote,
    comment, or dollar body is returned as the last statement. It is not
    an error here; the database reports it when the statement runs.
    """
    statements: list[str] = []
    # First real SQL character of the statement currently being read.
    # Stays None while we are between statements (whitespace and comments).
    statement_start: int | None = None
    index = 0
    script_length = len(script)

    while index < script_length:
        character = script[index]
        following = script[index + 1] if index + 1 < script_length else ""

        # "--" runs to the end of the line. A semicolon in there is not SQL.
        if character == "-" and following == "-":
            index = _skip_line_comment(script, index)
            continue

        # "/* */" may nest. A semicolon inside the comment is not SQL either.
        if character == "/" and following == "*":
            index = _skip_block_comment(script, index)
            continue

        # Standard string, or PostgreSQL E'...' where backslash escapes.
        if character == "'":
            if statement_start is None:
                statement_start = index
            index = _skip_quoted_literal(
                script,
                index,
                backslash_escapes=_quote_uses_backslash_escapes(script, index),
            )
            continue

        # Quoted identifier: "odd;name". Doubled quotes are one quote character.
        if character == '"':
            if statement_start is None:
                statement_start = index
            index = _skip_quoted_literal(script, index, backslash_escapes=False)
            continue

        # $$ ... $$ or $tag$ ... $tag$. "$1" is a placeholder, not a tag.
        if character == "$":
            opening_tag_end = _opening_dollar_tag_end(script, index)
            if opening_tag_end is not None:
                if statement_start is None:
                    statement_start = index
                index = _skip_dollar_quoted_body(script, index, opening_tag_end)
                continue

        # Semicolon between statements is only a separator. One after real
        # SQL closes that statement, including the semicolon itself.
        if character == ";":
            if statement_start is not None:
                statements.append(script[statement_start : index + 1])
                statement_start = None
            index += 1
            continue

        if statement_start is None and not character.isspace():
            statement_start = index
        index += 1

    if statement_start is not None:
        remainder = script[statement_start:].rstrip()
        if remainder:
            statements.append(remainder)
    return statements


def _is_identifier_character(character: str) -> bool:
    """Letters, digits, underscore, and non-ASCII (PostgreSQL identifiers)."""
    return character.isalnum() or character == "_" or ord(character) >= 128


def _skip_line_comment(script: str, index: int) -> int:
    """Index just past the newline, or the end of the script."""
    newline_at = script.find("\n", index)
    if newline_at < 0:
        return len(script)
    return newline_at + 1


def _skip_block_comment(script: str, index: int) -> int:
    """Index just past the matching ``*/``. Nested comments count.

    An unclosed comment runs to the end of the script.
    """
    depth = 0
    position = index
    script_length = len(script)
    while position < script_length:
        two_characters = script[position : position + 2]
        if two_characters == "/*":
            depth += 1
            position += 2
        elif two_characters == "*/":
            depth -= 1
            position += 2
            if depth == 0:
                return position
        else:
            position += 1
    return script_length


def _quote_uses_backslash_escapes(script: str, quote_index: int) -> bool:
    """True for PostgreSQL ``E'...'`` / ``e'...'``, not for ``name'...'``.

    The ``E`` has to be its own prefix. If a letter or digit sits in front
    of it, the quote is an ordinary string.
    """
    if quote_index < 1:
        return False
    prefix = script[quote_index - 1]
    if prefix not in {"E", "e"}:
        return False
    # "E" at the start of the script, or after a non-identifier, is a prefix.
    # "NAME'" is an ordinary string: the character before E is part of a word.
    prefix_stands_alone = quote_index < 2 or not _is_identifier_character(script[quote_index - 2])
    return prefix_stands_alone


def _skip_quoted_literal(script: str, index: int, *, backslash_escapes: bool) -> int:
    """Index just past the closing quote. The quote character is ``script[index]``.

    ``''`` or ``""`` is one escaped quote, not the end of the literal.
    ``E'...'`` also treats ``\\`` as an escape. An unclosed literal runs
    to the end of the script.
    """
    quote = script[index]
    position = index + 1
    script_length = len(script)
    while position < script_length:
        character = script[position]
        escaped_by_backslash = backslash_escapes and character == "\\"
        doubled_quote = (
            character == quote and position + 1 < script_length and script[position + 1] == quote
        )
        if escaped_by_backslash or doubled_quote:
            position += 2
            continue
        if character == quote:
            return position + 1
        position += 1
    return script_length


def _opening_dollar_tag_end(script: str, index: int) -> int | None:
    """Index of the ``$`` that closes the opening tag, or None if this is not one.

    ``$$`` and ``$body$`` are tags. ``$1`` is a parameter. ``a$b`` is not a
    tag either: a tag cannot start in the middle of an identifier.
    """
    if index >= 1 and _is_identifier_character(script[index - 1]):
        return None
    if index + 1 >= len(script):
        return None

    character_after_dollar = script[index + 1]
    if character_after_dollar == "$":
        return index + 1
    # "$1" and "$-" are not tags. A tag name starts with a letter or "_".
    if character_after_dollar.isdigit() or not _is_identifier_character(character_after_dollar):
        return None

    position = index + 2
    while position < len(script) and _is_identifier_character(script[position]):
        position += 1
    if position < len(script) and script[position] == "$":
        return position
    return None


def _skip_dollar_quoted_body(script: str, index: int, opening_tag_end: int) -> int:
    """Index just past the closing tag. Nothing inside the body is special.

    PostgreSQL does not treat quotes or comments inside ``$tag$ ... $tag$``
    as structure. The next copy of the same tag ends the body. A missing
    close runs to the end of the script.
    """
    tag = script[index : opening_tag_end + 1]
    body_starts_at = opening_tag_end + 1
    closing_tag_at = script.find(tag, body_starts_at)
    if closing_tag_at < 0:
        return len(script)
    return closing_tag_at + len(tag)
