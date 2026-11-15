import re
from pathlib import Path

from django.conf import settings

CATALOG = Path(settings.LOCALE_PATHS[0]) / 'es' / 'LC_MESSAGES' / 'django.po'
PLACEHOLDER = re.compile(r'%\((\w+)\)s')


def _entries():
    entries = []
    for block in CATALOG.read_text(encoding='utf-8').split('\n\n'):
        msgid = re.search(r'^msgid ((?:".*"\n?)+)', block, re.MULTILINE)
        msgstr = re.search(r'^msgstr ((?:".*"\n?)+)', block, re.MULTILINE)
        if not msgid or not msgstr:
            continue
        join = lambda raw: ''.join(re.findall(r'"(.*)"', raw))
        entries.append((join(msgid.group(1)), join(msgstr.group(1)), '#, fuzzy' in block))
    return [entry for entry in entries if entry[0]]


def test_every_message_has_a_spanish_translation():
    entries = _entries()

    assert entries
    assert [msgid for msgid, msgstr, _ in entries if not msgstr] == []


def test_no_translation_is_left_fuzzy():
    assert [msgid for msgid, _, fuzzy in _entries() if fuzzy] == []


def test_translations_keep_the_same_placeholders():
    mismatched = [
        msgid for msgid, msgstr, _ in _entries()
        if sorted(PLACEHOLDER.findall(msgid)) != sorted(PLACEHOLDER.findall(msgstr))
    ]

    assert mismatched == []
