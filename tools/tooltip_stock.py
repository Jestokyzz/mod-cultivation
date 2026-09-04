"""Bind Blizzard tooltip fields to their exact stock rank without freezing AP/glyphs.

This is a source transformation, NOT a reimplementation of the native formatter.
Client rendering remains a separate acceptance gate.
"""
from __future__ import annotations

import re

# Spell-scoped fields observed in the audited 3.3.5 source. Refuse unknown fields.
FIELD = re.compile(r'\$(?P<id>\d+)?(?P<field>[sSmMbBaAtToOqQeExX]\d+|[dDhHnNrRuUvViIfF])')
ATOM = re.compile(r'\$[lLgG][^;$\r\n]*;|\$(?:\d+)?[A-Za-z]+\d*')
DYNAMIC = {'$AP', '$ap', '$RWB', '$rwb', '$MWB', '$mwb', '$MW', '$mw', '$SP', '$sp'}
GRAMMAR = {'$l', '$L', '$g', '$G'}
VARIABLE = re.compile(r'\$<([A-Za-z][A-Za-z0-9]*)>')
STOCK_COLOR = 'FFD200'
PATH_OPEN = '{path}'
PATH_CLOSE = '{/path}'


def bind_stock_fields(text: str, base_id: int, *, definitions: bool = False) -> str:
    """Qualify field atoms, preserving existing cross-spell references verbatim."""
    def replace(match: re.Match) -> str:
        atom = match.group(0)
        # DescriptionVariable assignment names aren't numeric formatter fields.
        if definitions and match.end() < len(text) and text[match.end()] == '=':
            return atom
        if atom in DYNAMIC or atom in GRAMMAR or (atom[:2] in GRAMMAR and atom.endswith(';')):
            return atom
        parsed = FIELD.fullmatch(atom)
        if not parsed:
            raise ValueError(f'Unsupported stock token {atom!r} in spell {base_id}')
        return atom if parsed['id'] else f'${base_id}{parsed["field"]}'

    return ATOM.sub(replace, text)


def unbind_own_fields(text: str, base_id: int) -> str:
    """Canonicalize fields already qualified to this exact stock rank.

    Official rank strings inconsistently store otherwise identical fields as
    either ``$d`` or ``$1966d``. Inline source edits operate on one canonical
    stock template, while cross-spell references remain qualified.
    """
    def replace(match: re.Match) -> str:
        parsed = FIELD.fullmatch(match.group(0))
        if parsed and parsed['id'] == str(base_id):
            return '$' + parsed['field']
        return match.group(0)

    return ATOM.sub(replace, text)


def validate_variables(text: str, definitions: str) -> None:
    available = set(re.findall(r'^\$([A-Za-z][A-Za-z0-9]*)=', definitions, re.M))
    wanted = set(VARIABLE.findall(text)) | set(VARIABLE.findall(definitions))
    if wanted - available:
        raise ValueError(f'Undefined description variables: {sorted(wanted - available)}')


def player_text(text: str) -> str:
    """The old client's font must display numeric signs without fallback glyphs.

    Never run this over the Blizzard source/formatter expressions.
    Percent signs are literal: do not percent-format or double-escape them.
    """
    return text.replace('\u2212', '-')


def compose(base: str, addition: str, color: str, separator: str = ' ') -> str:
    if re.search(r'(?i)путь\s+(небожителя|ша)|(?:Celestial|Sha|Sage|Demon)\s*:', addition):
        raise ValueError('Forbidden path prefix in player-facing addition')
    if '$' in addition:
        raise ValueError('Path addition must be manifest text, not stock-bound formatter tokens')
    # Preserve Blizzard's mechanic text in its native yellow and append only
    # the path delta in the path color.  There is no blank separator or lower
    # path heading, so both pieces still read as one description.
    stock = base.rstrip()
    custom = player_text(addition.strip())
    if separator not in (' ', '\n'):
        raise ValueError(f'Invalid tooltip addition separator: {separator!r}')
    separator = separator if stock and custom else ''
    standard = f'|cff{STOCK_COLOR}{stock}|r' if stock else ''
    changed = f'|cff{color}{custom}|r' if custom else ''
    return standard + separator + changed


def exact(text: str, color: str) -> str:
    """Render an approved complete tooltip with explicit path-colored spans.

    Text outside ``{path}...{/path}`` remains Blizzard yellow.  Markers are
    source-only and are removed before the string reaches Spell.dbc.
    """
    clean = player_text(text.strip())
    visible = clean.replace(PATH_OPEN, '').replace(PATH_CLOSE, '')
    if re.search(r'(?i)путь\s+(небожителя|ша)|(?:Celestial|Sha|Sage|Demon)\s*:', visible):
        raise ValueError('Forbidden path prefix in player-facing tooltip')
    inside = False
    content = False
    for part in re.split(f'({re.escape(PATH_OPEN)}|{re.escape(PATH_CLOSE)})', clean):
        if part == PATH_OPEN:
            if inside:
                raise ValueError('Nested path-color markers are forbidden')
            inside, content = True, False
        elif part == PATH_CLOSE:
            if not inside or not content:
                raise ValueError('Unbalanced or empty path-color markers in complete tooltip')
            inside = False
        elif inside and part:
            content = True
    if inside:
        raise ValueError('Unbalanced path-color markers in complete tooltip')
    # Explicit complete descriptions may use the client's native formatter.
    # Unqualified fields intentionally resolve against the generated custom
    # rank, so one approved text remains interactive across the whole chain.
    rendered = clean.replace(PATH_OPEN, f'|r|cff{color}').replace(
        PATH_CLOSE, f'|r|cff{STOCK_COLOR}')
    trailing_stock = f'|r|cff{STOCK_COLOR}'
    if rendered.endswith(trailing_stock):
        rendered = rendered[:-len(trailing_stock)]
    result = f'|cff{STOCK_COLOR}{rendered}|r'
    empty_leading_stock = f'|cff{STOCK_COLOR}|r'
    if result.startswith(empty_leading_stock):
        result = result[len(empty_leading_stock):]
    return result
