from collections.abc import Callable

import customtkinter as ctk
from tkinterdnd2 import COPY, DND_FILES

from paperi.services.pipeline import SUPPORTED_EXTENSIONS

# A visibly different color while a drag hovers over the zone — a
# dropzone that looks identical whether or not it's about to accept a
# drop gives the user no confirmation it's even a live drop target
# (docs/stage5-ux-plan.md's post-launch UX fixes, point 15).
HOVER_FG_COLOR = ("#8ecae6", "#1f4e79")


def dropzone_caption(base_text: str) -> str:
    """base_text plus a line listing genuinely supported file types (point
    16) — spelled out so the user isn't left guessing what this will
    actually accept, rather than finding out only after a rejected drop."""
    types_line = " · ".join(ext.lstrip(".").upper() for ext in SUPPORTED_EXTENSIONS)
    return f"{base_text}\n{types_line}"


def wire_dropzone_dnd(
    widget: ctk.CTkLabel,
    on_files_dropped: Callable[[list[str]], None],
    normal_fg_color: tuple[str, str] | str,
) -> None:
    """Registers `widget` as a file drop target with hover feedback.

    Also fixes a real (if latent) protocol-compliance gap: tkinterdnd2's
    own docs say <<DropEnter>>/<<DropPosition>>/<<Drop>> callbacks "should
    always return an action" (COPY/MOVE/LINK/ASK/PRIVATE) — the original
    binding was a bare lambda forwarding on_files_dropped's return value,
    which is always None (it's a void callback), technically leaving the
    drop unacknowledged rather than explicitly accepted as a copy."""
    widget.drop_target_register(DND_FILES)

    def handle_enter(_event: object) -> str:
        widget.configure(fg_color=HOVER_FG_COLOR)
        return COPY

    def handle_leave(_event: object) -> None:
        widget.configure(fg_color=normal_fg_color)

    def handle_drop(event: object) -> str:
        widget.configure(fg_color=normal_fg_color)
        on_files_dropped(list(widget.tk.splitlist(event.data)))  # type: ignore[attr-defined]
        return COPY

    widget.dnd_bind("<<DropEnter>>", handle_enter)
    widget.dnd_bind("<<DropLeave>>", handle_leave)
    widget.dnd_bind("<<Drop>>", handle_drop)
