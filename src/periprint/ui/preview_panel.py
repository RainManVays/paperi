import customtkinter as ctk


class PreviewPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, **kwargs):
        super().__init__(master, **kwargs)

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
            fit_row, text="по ширине", variable=self.fit_mode_var, value="fit_width"
        ).pack(side="left")
        ctk.CTkRadioButton(
            fit_row, text="как есть", variable=self.fit_mode_var, value="actual_size"
        ).pack(side="left", padx=(8, 0))

        self.dithering_var = ctk.BooleanVar(value=True)
        self.dithering_checkbox = ctk.CTkCheckBox(
            self, text="Дизеринг", variable=self.dithering_var
        )
        self.dithering_checkbox.pack(anchor="w", padx=8, pady=8)
