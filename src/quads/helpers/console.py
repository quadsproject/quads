from rich.console import Console


def make_console(**kwargs) -> Console:
    """Build a Rich console that never applies emoji substitution.

    Rich defaults to emoji=True, which rewrites colon-delimited data such as
    MAC octets ("...:ab:...") into emoji. QUADS output carries raw data, so
    every console - explicit, Progress or otherwise - must keep that channel
    off; this factory makes the invariant structural instead of a convention.
    """
    kwargs["emoji"] = False
    return Console(**kwargs)
