from collections.abc import Callable

import customtkinter as ctk
import PIL.Image

_MAX_PREVIEW_WIDTH_PX = 260


class PreviewPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_settings_changed: Callable[[], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._on_settings_changed = on_settings_changed
        self._preview_image_ref: ctk.CTkImage | None = None

        title = ctk.CTkLabel(self, text="ПРЕВЬЮ", font=ctk.CTkFont(weight="bold"))
        title.pack(anchor="w", padx=8, pady=(8, 0))

        self.preview_area = ctk.CTkLabel(
            self,
            text="(нет документа)",
            fg_color=("gray90", "gray15"),
            height=220,
        )
        self.preview_area.pack(fill="both", expand=True, padx=8, pady=8)

        settings_title = ctk.CTkLabel(
            self, text="Настройки печати:", font=ctk.CTkFont(weight="bold")
        )
        settings_title.pack(anchor="w", padx=8, pady=(8, 0))

        self.concentration_slider = ctk.CTkSlider(self, from_=0, to=2, number_of_steps=2)
        self.concentration_slider.set(1)
        self.concentration_slider.pack(fill="x", padx=8, pady=(4, 0))

        self.break_slider = ctk.CTkSlider(self, from_=0, to=255)
        self.break_slider.set(60)
        self.break_slider.pack(fill="x", padx=8, pady=(4, 0))

        self.fit_mode_var = ctk.StringVar(value="fit_width")
        fit_row = ctk.CTkFrame(self, fg_color="transparent")
        fit_row.pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkRadioButton(
            fit_row,
            text="по ширине",
            variable=self.fit_mode_var,
            value="fit_width",
            command=self._handle_settings_changed,
        ).pack(side="left")
        ctk.CTkRadioButton(
            fit_row,
            text="как есть",
            variable=self.fit_mode_var,
            value="actual_size",
            command=self._handle_settings_changed,
        ).pack(side="left", padx=(8, 0))

        self.dithering_var = ctk.BooleanVar(value=True)
        self.dithering_checkbox = ctk.CTkCheckBox(
            self,
            text="Дизеринг",
            variable=self.dithering_var,
            command=self._handle_settings_changed,
        )
        self.dithering_checkbox.pack(anchor="w", padx=8, pady=8)

    def _handle_settings_changed(self) -> None:
        if self._on_settings_changed:
            self._on_settings_changed()

    def show_preview(self, image: PIL.Image.Image) -> None:
        if image.width > _MAX_PREVIEW_WIDTH_PX:
            ratio = _MAX_PREVIEW_WIDTH_PX / image.width
            display_size = (_MAX_PREVIEW_WIDTH_PX, max(1, round(image.height * ratio)))
        else:
            display_size = (image.width, image.height)

        # CTkImage resizes via plain PIL .resize() with no resample filter.
        # PIL can't properly interpolate mode "1" (1-bit) images, so
        # downscaling the already-dithered raster directly produces moiré
        # noise. Converting to "L" first lets the resize average the
        # dithered dots into smooth gray — closer to how the real printout
        # reads from a normal viewing distance anyway.
        display_image = image.convert("L") if image.mode == "1" else image

        self._preview_image_ref = ctk.CTkImage(
            light_image=display_image, dark_image=display_image, size=display_size
        )
        self.preview_area.configure(image=self._preview_image_ref, text="")

    def show_message(self, text: str) -> None:
        self._preview_image_ref = None
        self.preview_area.configure(image=None, text=text)
