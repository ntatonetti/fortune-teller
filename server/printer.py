"""Fortune cards on a USB ESC/POS thermal printer (or the terminal, for testing)."""

import logging
import textwrap

from . import config
from .models import Fortune

log = logging.getLogger("printer")

FOOTER = "VOID AFTER MIDNIGHT"

# Thermal printers only know single-byte codepages, which lack typographic punctuation
# (CP437 has no curly quotes or dashes), so print plain ASCII stand-ins on every model.
_PLAIN = str.maketrans({"\u2026": "...", "\u2014": "--", "\u2013": "-", "\u2018": "'", "\u2019": "'",
                        "\u201c": '"', "\u201d": '"', "\u00a0": " "})


def plain(s: str) -> str:
    return s.translate(_PLAIN)


def _short(question: str, limit: int = 90) -> str:
    return question if len(question) <= limit else question[: limit - 1].rsplit(" ", 1)[0] + "…"


def card_lines(f: Fortune, width: int) -> list[str]:
    wrap = lambda s: textwrap.wrap(s, width) or [""]  # noqa: E731
    rule = "~" * width
    lines = [rule, config.ORACLE_NAME.upper().center(width), "* Clockwork Oracle *".center(width), rule, ""]
    lines += [l.center(width) for l in wrap(f.card_title.upper())]
    if f.question:
        lines += ["", "You asked:"] + wrap(f'"{_short(f.question)}"')
    lines += [""] + wrap(f.card_text) + [""]
    lines += ["Your task tonight:"] + wrap(f.task) + [""]
    lines += [f"Lucky number: {f.lucky_number}".center(width), "", rule, FOOTER.center(width), rule]
    return lines


def _print_usb(f: Fortune) -> None:
    from escpos.printer import Usb  # imported lazily: needs libusb only when printing for real

    p = Usb(config.PRINTER_USB_VENDOR, config.PRINTER_USB_PRODUCT,
            in_ep=config.PRINTER_USB_IN_EP, out_ep=config.PRINTER_USB_OUT_EP)
    width = config.PRINTER_WIDTH_CHARS
    f = f.model_copy(update={k: plain(getattr(f, k)) for k in ("card_title", "card_text", "task", "question")
                             if getattr(f, k)})
    try:
        p.set(align="center", bold=True, double_height=True, double_width=True)
        p.text(config.ORACLE_NAME.upper() + "\n")
        p.set(align="center", bold=False, normal_textsize=True)
        p.text("* Clockwork Oracle *\n" + "~" * width + "\n\n")
        p.set(align="center", bold=True)
        p.text("\n".join(textwrap.wrap(f.card_title.upper(), width)) + "\n\n")
        p.set(align="left", bold=False)
        if f.question:
            p.text("You asked:\n" + "\n".join(textwrap.wrap(plain(f'"{_short(f.question)}"'), width)) + "\n\n")
        p.text("\n".join(textwrap.wrap(f.card_text, width)) + "\n\n")
        p.set(bold=True)
        p.text("Your task tonight:\n")
        p.set(bold=False)
        p.text("\n".join(textwrap.wrap(f.task, width)) + "\n\n")
        p.set(align="center", bold=True, double_height=True)
        p.text(f"Lucky number: {f.lucky_number}\n")
        p.set(align="center", bold=False, normal_textsize=True)
        p.text("~" * width + "\n" + FOOTER + "\n")
        p.cut()
    finally:
        p.close()


def print_card(f: Fortune) -> str:
    """Blocking. Returns a short status string."""
    if config.PRINTER == "none":
        return "disabled"
    if config.PRINTER == "console":
        print("\n".join(card_lines(f, config.PRINTER_WIDTH_CHARS)), flush=True)
        return "console"
    try:
        _print_usb(f)
        return "printed"
    except Exception as e:  # the show must go on if the printer jams or is unplugged
        log.error("Printer failed: %s", e)
        return f"error: {e}"
