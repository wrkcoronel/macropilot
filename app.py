from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from models import Macro, MacroStep
from player import MacroPlayer
from recorder import MacroRecorder
from storage import (
    load_macro_from_path,
    save_macro_default,
    save_macro_to_path,
    load_theme,
    save_theme,
)
from utils import ensure_dir, generate_id, get_app_storage_dir, now_iso, parse_repetitions, parse_speed


class MacroPilotApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.app_version = "alfa 1.0"

        self.title(f"MacroPilot {self.app_version}")
        self.geometry("980x620")
        self.minsize(900, 560)

        base_dir = Path(__file__).resolve().parent
        storage_dir = get_app_storage_dir("MacroPilot", base_dir)
        self.storage_dir = ensure_dir(storage_dir)
        self.macros_dir = ensure_dir(self.storage_dir / "macros")

        # load persisted theme if present
        try:
            saved = load_theme(self.storage_dir)
            if saved in ("dark", "light"):
                ctk.set_appearance_mode(saved)
        except Exception:
            pass

        self.recorder = MacroRecorder()
        self.player = MacroPlayer()
        self.current_macro = Macro(
            id=generate_id(),
            name="Nova Macro",
            created_at=now_iso(),
            steps=[],
        )

        self.status_var = ctk.StringVar(value="Pronto")
        self.speed_var = ctk.StringVar(value="1x")
        self.repetitions_var = ctk.StringVar(value="1")
        self.name_var = ctk.StringVar(value="Nova Macro")
        self._record_append_mode = False

        self._build_layout()
        self.refresh_steps()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, corner_radius=10)
        left.grid(row=0, column=0, padx=12, pady=12, sticky="ns")

        right = ctk.CTkFrame(self, corner_radius=10)
        right.grid(row=0, column=1, padx=(0, 12), pady=12, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="MacroPilot", font=ctk.CTkFont(size=22, weight="bold")).pack(
            pady=(18, 10), padx=16
        )
        ctk.CTkLabel(left, text=f"Versão {self.app_version}", text_color="red").pack(
            pady=(0, 10), padx=16
        )

        ctk.CTkLabel(left, text="Nome da macro").pack(anchor="w", padx=16)
        self.name_entry = ctk.CTkEntry(left, textvariable=self.name_var, width=210)
        self.name_entry.pack(padx=16, pady=(4, 12))

        self.btn_record = ctk.CTkButton(left, text="Gravar", command=self.handle_record)
        self.btn_record.pack(fill="x", padx=16, pady=4)

        self.btn_record_continue = ctk.CTkButton(
            left,
            text="Continuar Fluxo",
            command=self.handle_continue_record,
        )
        self.btn_record_continue.pack(fill="x", padx=16, pady=4)

        self.btn_stop = ctk.CTkButton(left, text="Parar", command=self.handle_stop)
        self.btn_stop.pack(fill="x", padx=16, pady=4)

        self.btn_save = ctk.CTkButton(left, text="Salvar", command=self.handle_save)
        self.btn_save.pack(fill="x", padx=16, pady=4)

        self.btn_play = ctk.CTkButton(left, text="Reproduzir", command=self.handle_play, fg_color="#008B3F")
        self.btn_play.pack(fill="x", padx=16, pady=4)

        self.btn_import = ctk.CTkButton(left, text="Importar", command=self.handle_import)
        self.btn_import.pack(fill="x", padx=16, pady=4)

        self.btn_export = ctk.CTkButton(left, text="Exportar", command=self.handle_export)
        self.btn_export.pack(fill="x", padx=16, pady=4)

        self.btn_theme = ctk.CTkButton(left, text="Config", command=self.handle_theme)
        self.btn_theme.pack(fill="x", padx=16, pady=4)

        self.btn_clear = ctk.CTkButton(left, text="Limpar", command=self.handle_clear, fg_color="#8B0000")
        self.btn_clear.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(left, text="Velocidade").pack(anchor="w", padx=16, pady=(12, 0))
        self.speed_menu = ctk.CTkOptionMenu(
            left,
            values=["0.5x", "1x", "2x", "3x"],
            variable=self.speed_var,
        )
        self.speed_menu.pack(fill="x", padx=16, pady=(4, 8))

        ctk.CTkLabel(left, text="Repetições").pack(anchor="w", padx=16)
        self.repetitions_entry = ctk.CTkEntry(left, textvariable=self.repetitions_var)
        self.repetitions_entry.pack(fill="x", padx=16, pady=(4, 12))

        ctk.CTkLabel(left, text="ESC cancela execução", text_color="gray70").pack(
            anchor="w", padx=16, pady=(4, 14)
        )

        ctk.CTkLabel(left, textvariable=self.status_var, wraplength=210, justify="left").pack(
            anchor="w", padx=16, pady=(0, 18)
        )

        ctk.CTkLabel(
            right,
            text="Passos da Macro",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))

        self.steps_frame = ctk.CTkScrollableFrame(right)
        self.steps_frame.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.steps_frame.grid_columnconfigure(0, weight=1)

    def handle_record(self) -> None:
        self._start_recording(append_mode=False)

    def handle_continue_record(self) -> None:
        self._start_recording(append_mode=True)

    def _start_recording(self, append_mode: bool) -> None:
        if self.player.is_playing:
            messagebox.showwarning("MacroPilot", "Pare a reprodução antes de gravar.")
            return

        if self.recorder.is_recording:
            messagebox.showinfo("MacroPilot", "A gravação já está em andamento.")
            return

        try:
            self._record_append_mode = append_mode
            self.recorder.start(self.name_var.get())
            if append_mode:
                self.status_var.set("Gravando continuação... use o botão Parar para anexar ao fluxo atual.")
            else:
                self.status_var.set("Gravando... use o botão Parar para finalizar.")
        except Exception as error:
            self._record_append_mode = False
            messagebox.showerror("Erro", f"Falha ao iniciar gravação: {error}")

    def handle_stop(self) -> None:
        if self.recorder.is_recording:
            try:
                macro = self.recorder.stop()
                macro.name = self.name_var.get().strip() or macro.name

                if self._record_append_mode:
                    self.current_macro.name = self.name_var.get().strip() or self.current_macro.name
                    self.current_macro.steps.extend(macro.steps)
                    self.status_var.set("Continuação gravada e anexada ao fluxo atual.")
                else:
                    self.current_macro = macro
                    self.status_var.set("Gravação finalizada. Use Salvar ou Exportar para persistir.")

                self.refresh_steps()
            except Exception as error:
                messagebox.showerror("Erro", f"Falha ao parar gravação: {error}")
            finally:
                self._record_append_mode = False
            return

        if self.player.is_playing:
            self.player.stop()
            self.status_var.set("Cancelamento solicitado...")
            return

        self.status_var.set("Nada em execução no momento.")

    def handle_save(self) -> None:
        if not self.current_macro.steps:
            messagebox.showwarning("MacroPilot", "Não há passos para salvar.")
            return

        self.current_macro.name = self.name_var.get().strip() or self.current_macro.name

        try:
            save_path = save_macro_default(self.current_macro, self.macros_dir)
            self.status_var.set(f"Macro salva em {save_path.name}")
        except Exception as error:
            messagebox.showerror("Erro", f"Falha ao salvar macro: {error}")

    def handle_play(self) -> None:
        if self.recorder.is_recording:
            messagebox.showwarning("MacroPilot", "Pare a gravação antes de reproduzir.")
            return

        if not self.current_macro.steps:
            messagebox.showwarning("MacroPilot", "Não há passos para reproduzir.")
            return

        try:
            speed = parse_speed(self.speed_var.get())
            repetitions = parse_repetitions(self.repetitions_var.get())
        except Exception as error:
            messagebox.showerror("Erro", f"Parâmetros inválidos: {error}")
            return

        try:
            self.player.play_async(
                macro=self.current_macro,
                speed=speed,
                repetitions=repetitions,
                initial_delay=5.0,
                on_step=self._on_step_from_thread,
                on_finish=self._on_finish_from_thread,
                on_error=self._on_error_from_thread,
            )
            self.status_var.set(
                f"Iniciando em 5s... depois executa {repetitions}x em {self.speed_var.get()}. ESC cancela."
            )
        except Exception as error:
            messagebox.showerror("Erro", f"Falha ao iniciar reprodução: {error}")

    def handle_import(self) -> None:
        path = filedialog.askopenfilename(
            title="Importar macro",
            initialdir=self.macros_dir,
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return

        try:
            macro = load_macro_from_path(Path(path))
            self.current_macro = macro
            self.name_var.set(macro.name)
            self.refresh_steps()
            self.status_var.set(f"Macro importada: {Path(path).name}")
        except Exception as error:
            messagebox.showerror("Erro", f"Falha ao importar macro: {error}")

    def handle_export(self) -> None:
        if not self.current_macro.steps:
            messagebox.showwarning("MacroPilot", "Não há passos para exportar.")
            return

        self.current_macro.name = self.name_var.get().strip() or self.current_macro.name

        path = filedialog.asksaveasfilename(
            title="Exportar macro",
            initialdir=self.macros_dir,
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"{self.current_macro.name}.json",
        )
        if not path:
            return

        try:
            save_macro_to_path(self.current_macro, Path(path))
            self.status_var.set(f"Macro exportada: {Path(path).name}")
        except Exception as error:
            messagebox.showerror("Erro", f"Falha ao exportar macro: {error}")

    def handle_theme(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Tema")
        dialog.geometry("320x160")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Escolha o tema", font=ctk.CTkFont(size=14, weight="bold")).pack(
            pady=(12, 8)
        )

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(8, 12))
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)

        def set_theme(mode: str) -> None:
            try:
                ctk.set_appearance_mode(mode)
                save_theme(mode, self.storage_dir)
                self.status_var.set("Tema alterado para Preto." if mode == "dark" else "Tema alterado para Branco.")
            except Exception as error:
                messagebox.showerror("Erro", f"Não foi possível salvar o tema: {error}")
            finally:
                dialog.destroy()

        ctk.CTkButton(buttons, text="Preto", command=lambda: set_theme("dark")).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkButton(buttons, text="Branco", command=lambda: set_theme("light")).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        dialog.bind("<Escape>", lambda _: dialog.destroy())

    def handle_clear(self) -> None:
        if not self.current_macro.steps:
            messagebox.showinfo("MacroPilot", "Não há passos para limpar.")
            return

        result = messagebox.askyesno(
            "Confirmar",
            "Tem certeza que deseja remover todos os passos da macro?",
        )
        if result:
            self.current_macro.steps.clear()
            self.status_var.set("Macro limpa.")
            self.refresh_steps()

    def refresh_steps(self) -> None:
        for widget in self.steps_frame.winfo_children():
            widget.destroy()

        if not self.current_macro.steps:
            ctk.CTkLabel(self.steps_frame, text="Nenhum passo gravado.").grid(
                row=0, column=0, padx=10, pady=10, sticky="w"
            )
            return

        for idx, step in enumerate(self.current_macro.steps, start=1):
            row = ctk.CTkFrame(self.steps_frame)
            row.grid(row=idx - 1, column=0, sticky="ew", padx=8, pady=6)
            row.grid_columnconfigure(1, weight=1)
            row.grid_columnconfigure(2, weight=0)
            row.grid_columnconfigure(3, weight=0)
            row.grid_columnconfigure(4, weight=0)
            row.grid_columnconfigure(5, weight=0)

            index_label = ctk.CTkLabel(row, text=f"{idx}", width=32)
            index_label.grid(row=0, column=0, padx=(8, 6), pady=8)

            if step.type in ("click", "scroll"):
                info_label = ctk.CTkLabel(
                    row,
                    text=f"{step.type.upper()} - coordenada ({step.x}, {step.y}) | delay: {step.delay_after:.2f}s",
                    anchor="w",
                    justify="left",
                )
                info_label.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(6, 4), pady=8)

                edit_handler = lambda _event, step_id=step.id: self.edit_step_coordinates(step_id)
                index_label.bind("<Button-1>", edit_handler)
                info_label.bind("<Button-1>", edit_handler)
            else:
                ctk.CTkLabel(
                    row,
                    text=f"{step.type.upper()} - {step.summary} | delay: {step.delay_after:.2f}s",
                    anchor="w",
                    justify="left",
                ).grid(row=0, column=1, columnspan=2, sticky="ew", padx=6, pady=8)

            ctk.CTkButton(
                row,
                text="↑",
                width=36,
                command=lambda step_id=step.id: self.move_step(step_id, -1),
            ).grid(row=0, column=3, padx=(6, 4), pady=8)

            ctk.CTkButton(
                row,
                text="↓",
                width=36,
                command=lambda step_id=step.id: self.move_step(step_id, 1),
            ).grid(row=0, column=4, padx=4, pady=8)

            ctk.CTkButton(
                row,
                text="Deletar",
                width=80,
                command=lambda step_id=step.id: self.delete_step(step_id),
            ).grid(row=0, column=5, padx=(6, 8), pady=8)

    def edit_step_coordinates(self, step_id: str) -> None:
        if self.recorder.is_recording:
            messagebox.showwarning("MacroPilot", "Pare a gravação antes de editar coordenadas.")
            return

        if self.player.is_playing:
            messagebox.showwarning("MacroPilot", "Pare a reprodução antes de editar coordenadas.")
            return

        step = self._find_step(step_id)
        if step is None:
            messagebox.showerror("Erro", "Passo não encontrado.")
            return

        if step.type not in ("click", "scroll"):
            messagebox.showinfo("MacroPilot", "Este tipo de passo não possui coordenada editável.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Editar Coordenadas")
        dialog.geometry("360x230")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        x_var = ctk.StringVar(value=str(int(step.x or 0)))
        y_var = ctk.StringVar(value=str(int(step.y or 0)))

        ctk.CTkLabel(dialog, text="Coordenada X").pack(anchor="w", padx=16, pady=(16, 4))
        x_entry = ctk.CTkEntry(dialog, textvariable=x_var)
        x_entry.pack(fill="x", padx=16)

        ctk.CTkLabel(dialog, text="Coordenada Y").pack(anchor="w", padx=16, pady=(12, 4))
        y_entry = ctk.CTkEntry(dialog, textvariable=y_var)
        y_entry.pack(fill="x", padx=16)

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(20, 12))
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)

        def save() -> None:
            try:
                new_x = int(x_var.get().strip())
                new_y = int(y_var.get().strip())
            except ValueError:
                messagebox.showerror("Erro", "As coordenadas devem ser números inteiros.")
                return

            step.x = new_x
            step.y = new_y
            self.status_var.set(f"Coordenada atualizada para ({new_x}, {new_y}).")
            dialog.destroy()
            self.refresh_steps()

        ctk.CTkButton(buttons, text="Cancelar", command=dialog.destroy, height=34).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 6),
            pady=(0, 2),
        )
        ctk.CTkButton(buttons, text="Salvar", command=save, height=34).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(6, 0),
            pady=(0, 2),
        )

        dialog.bind("<Return>", lambda _: save())
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        x_entry.focus_set()

    def _find_step(self, step_id: str) -> MacroStep | None:
        for step in self.current_macro.steps:
            if step.id == step_id:
                return step
        return None

    def move_step(self, step_id: str, direction: int) -> None:
        steps = self.current_macro.steps
        current_index = next((index for index, step in enumerate(steps) if step.id == step_id), None)
        if current_index is None:
            return

        target_index = current_index + direction
        if target_index < 0 or target_index >= len(steps):
            return

        steps[current_index], steps[target_index] = steps[target_index], steps[current_index]
        self.status_var.set(f"Passo movido para posição {target_index + 1}.")
        self.refresh_steps()

    def delete_step(self, step_id: str) -> None:
        before = len(self.current_macro.steps)
        self.current_macro.remove_step(step_id)
        after = len(self.current_macro.steps)

        if after < before:
            self.status_var.set("Passo removido.")
            self.refresh_steps()

    def _on_step_from_thread(self, repetition: int, step_index: int, step) -> None:
        self.after(
            0,
            lambda: self.status_var.set(
                f"Execução {repetition} | passo {step_index}: {step.type}"
            ),
        )

    def _on_finish_from_thread(self, cancelled: bool) -> None:
        self.after(
            0,
            lambda: self.status_var.set(
                "Execução interrompida." if cancelled else "Execução concluída."
            ),
        )

    def _on_error_from_thread(self, error: Exception) -> None:
        self.after(0, lambda: messagebox.showerror("Erro", f"Falha na execução: {error}"))

    def _on_close(self) -> None:
        try:
            if self.recorder.is_recording:
                self.recorder.stop()
            if self.player.is_playing:
                self.player.stop()
        finally:
            self.destroy()


def main() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = MacroPilotApp()
    app.mainloop()


if __name__ == "__main__":
    main()
