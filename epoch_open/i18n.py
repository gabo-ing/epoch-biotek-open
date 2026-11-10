"""Which language the programs speak, and the machinery for switching it.

The interface began in Spanish, because that is the language of the lab the
instrument sits in. Putting it on GitHub changed who else might run it, and a
reader somebody cannot operate is no more use to them than one with no
licence. So the text is now kept per language and chosen at startup.

English is the default. Not because it is the better language for this lab --
it is not, and `epoch_open.json` here says `"language": "es"` -- but because a
stranger who downloads this cannot read a dialog that tells them how to change
the language. A Spanish lab sets it once; everyone else gets something they
can read without being told.

**The mechanism.** A module keeps its `TEXT` (or `MESSAGES`) dict exactly as
before and registers the per-language tables against it:

    TEXTS = {"en": _EN, "es": _ES}
    TEXT = register({}, TEXTS)

`register` fills the dict in place and remembers it. `set_language()` refills
every registered dict, again in place. Nothing is ever rebound, so the two
hundred-odd `TEXT["key"]` call sites stay exactly as they were, and a module
that did `from .gui import TEXT` would still see the change.

**Order matters once.** Widgets copy their text when they are built, so the
language has to be settled before any window is constructed. `launch.py` does
that before importing a GUI. Changing the setting afterwards writes it to the
configuration and takes effect on restart; the alternative, re-rendering a
live window, buys very little for a program somebody opens once a morning.
"""

# What a language is called in its own language, for the preferences dropdown.
# A person looking for their own language is not helped by reading its name in
# someone else's.
LANGUAGES = {
    "en": "English",
    "es": "Espanol",
}

DEFAULT = "en"

_current = DEFAULT

# Every (live dict, {language: table}) pair handed to `register`.
_registered: list[tuple[dict, dict]] = []


def normalise(code) -> str:
    """The language actually used for `code`, which may be nonsense.

    A configuration file is a text file a person edits, so it will eventually
    contain `"language": "english"`, or `"EN "`, or a typo. None of those is
    worth an error dialog in front of someone who wants to read a plate: the
    program falls back to the default and carries on.
    """
    if not isinstance(code, str):
        return DEFAULT
    code = code.strip().lower().replace("_", "-")
    if code in LANGUAGES:
        return code
    # "es-CL", "en-GB": the region is irrelevant here, the language is not.
    base = code.split("-")[0]
    if base in LANGUAGES:
        return base
    return DEFAULT


def current() -> str:
    """The language in force."""
    return _current


def _fill(live: dict, tables: dict) -> None:
    """Fill `live` with the best table available, never with nothing.

    Current language, then the default, then whatever the table does have.
    The last step matters: a table translated into only one language, or a
    half-finished one being worked on, must still produce a readable screen
    rather than a window of blanks and KeyErrors.
    """
    table = tables.get(_current)
    if table is None:
        table = tables.get(DEFAULT)
    if table is None:
        table = next(iter(tables.values()), {})
    live.clear()
    live.update(table)


def register(live: dict, tables: dict) -> dict:
    """Fill `live` from `tables` now, and again whenever the language changes.

    Returns `live`, so a module can write `TEXT = register({}, TEXTS)`.
    """
    _registered.append((live, tables))
    _fill(live, tables)
    return live


def set_language(code) -> str:
    """Switch language, refill every registered table, return what was used."""
    global _current
    _current = normalise(code)
    for live, tables in _registered:
        _fill(live, tables)
    return _current


def missing_keys() -> dict[str, set]:
    """Keys one language has and another lacks, per registered table.

    A missing key is a KeyError in front of a technician, at whatever moment
    the program first needs that particular sentence -- which in practice is
    the moment something has already gone wrong. The test suite calls this so
    that a translation can be incomplete on disk but never in a release.
    """
    out = {}
    for index, (_live, tables) in enumerate(_registered):
        languages = {code: set(table) for code, table in tables.items()}
        every = set().union(*languages.values()) if languages else set()
        gaps = {code: every - keys
                for code, keys in languages.items() if every - keys}
        if gaps:
            out[f"table{index}"] = gaps
    return out


def tables() -> list[tuple[dict, dict]]:
    """Every registered pair, for the tests that check the two languages."""
    return list(_registered)
