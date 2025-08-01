#!/usr/bin/env python3
"""invoice_flatten_merge.py – GUI Edition – v1.4.2

Drag‑and‑drop tool that pairs PDFs containing "Cover Sheet" and "Invoice" in
their file names. Each cover sheet is flattened and merged with its invoice to
produce a single **fully flattened** two‑page PDF. Includes both a GUI for
casual users and a CLI fallback for power users.

v1.4.2 – Fixed syntax errors and duplicated code
• Fixed import statement syntax errors
• Removed duplicated code sections
• Enhanced error handling for Ghostscript operations
• Added better file validation
"""

from __future__ import annotations
import os
import subprocess
import sys
import threading
import queue
from pathlib import Path
from typing import List, Optional
import platform
import re

try:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox
    from tkinterdnd2 import DND_FILES, TkinterDnD
    from PIL import Image, ImageTk
    from PyPDF2 import PdfReader, PdfWriter
    GUI_AVAILABLE = True
except ImportError as e:
    GUI_AVAILABLE = False
    print(f"Warning: GUI dependencies not available: {e}")
    print("Running in CLI mode only.")

# ────────────────────────────────────────────────────────────
# Paths & constants
# ────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
LOGO_DIR = ROOT_DIR / "_GUI-Logos"
PRIMARY_LOGO = LOGO_DIR / "Arch Aerial Logo White.png"
CIRCLE_LOGO = LOGO_DIR / "AALLC_CircleLogo_2023_V3_White.png"

# Keywords to identify PDFs
COVER_KEYWORD = "cover sheet"
INVOICE_KEYWORD = "invoice"
DEFAULT_OUTPUT = "FINAL_MERGED_INVOICE.pdf"

# ────────────────────────────────────────────────────────────
# Ghostscript helper
# ────────────────────────────────────────────────────────────

def ghostscript_exe() -> str:
    """Return the path to the Ghostscript executable bundled with the app or
    available on the system."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        if os.name == "nt":
            vend = Path(base) / "ghostscript" / "gswin64c.exe"
        else:
            vend = Path(base) / "ghostscript" / "gs"
        if vend.is_file():
            return str(vend)
    
    # Try to find system Ghostscript
    if os.name == "nt":
        # Windows: try common locations
        gs_names = ["gswin64c.exe", "gswin32c.exe", "gs.exe"]
        common_paths = [
            Path("C:/Program Files/gs"),
            Path("C:/Program Files (x86)/gs"),
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "gs",
        ]
        
        for base_path in common_paths:
            if base_path.exists():
                for item in base_path.iterdir():
                    if item.is_dir() and item.name.startswith("gs"):
                        for gs_name in gs_names:
                            gs_path = item / "bin" / gs_name
                            if gs_path.exists():
                                return str(gs_path)
        
        # Fall back to expecting it in PATH
        return "gswin64c"
    else:
        # Unix-like systems
        return "gs"


def check_ghostscript() -> bool:
    """Check if Ghostscript is available."""
    try:
        cmd = [ghostscript_exe(), "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def gs_flatten(src: Path, dst: Path) -> None:
    """Flatten a PDF using Ghostscript."""
    if not src.exists():
        raise FileNotFoundError(f"Source PDF not found: {src}")
    
    cmd = [
        ghostscript_exe(),
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.6",
        "-dPDFSETTINGS=/printer",
        "-dPrinted",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={dst}",
        str(src),
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        error_msg = f"Ghostscript failed: {e.stderr if e.stderr else str(e)}"
        raise RuntimeError(error_msg)
    except FileNotFoundError:
        raise RuntimeError(
            "Ghostscript not found. Please install Ghostscript:\n"
            "• Windows: https://www.ghostscript.com/download/gsdnld.html\n"
            "• Mac: brew install ghostscript\n"
            "• Linux: sudo apt-get install ghostscript"
        )

# ────────────────────────────────────────────────────────────
# PDF helpers
# ────────────────────────────────────────────────────────────

def is_valid_pdf(filepath: Path) -> bool:
    """Check if a file is a valid PDF."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(5)
            return header == b'%PDF-'
    except Exception:
        return False


def merge_pdfs(first: Path, second: Path, out_pdf: Path) -> None:
    """Merge two PDFs into *out_pdf*."""
    if not first.exists() or not second.exists():
        raise FileNotFoundError("One or both input PDFs not found")
    
    writer = PdfWriter()
    
    for pdf_path in (first, second):
        try:
            reader = PdfReader(str(pdf_path))
            for page in reader.pages:
                writer.add_page(page)
        except Exception as e:
            raise RuntimeError(f"Error reading {pdf_path.name}: {str(e)}")
    
    try:
        with out_pdf.open("wb") as fh:
            writer.write(fh)
    except Exception as e:
        raise RuntimeError(f"Error writing output PDF: {str(e)}")



def pair_cover_invoices(pdfs: List[Path]) -> List[tuple[Path, Path]]:
    """Return (cover, invoice) pairs from *pdfs* based on keywords."""
    def sanitize(name: str) -> str:
        base = name.lower()
        base = base.replace(COVER_KEYWORD, "")
        base = base.replace(INVOICE_KEYWORD, "")
        base = re.sub(r"[\s_-]+", "", base)
        return base

    groups: dict[str, dict[str, Path]] = {}
    for pdf in pdfs:
        stem = pdf.stem.lower()
        key = sanitize(stem)
        entry = groups.setdefault(key, {})
        if COVER_KEYWORD in stem:
            entry["cover"] = pdf
        if INVOICE_KEYWORD in stem:
            entry["invoice"] = pdf

    pairs = []
    for entry in groups.values():
        cover = entry.get("cover")
        invoice = entry.get("invoice")
        if cover and invoice:
            pairs.append((cover, invoice))
    return pairs

# ────────────────────────────────────────────────────────────
# GUI
# ────────────────────────────────────────────────────────────

if GUI_AVAILABLE:
    class InvoiceMergeGUI(TkinterDnD.Tk):
        """Main application window."""

        def __init__(self) -> None:
            super().__init__()
            ctk.set_appearance_mode("Dark")
            ctk.set_default_color_theme("blue")
            self.title("Arch Aerial – Invoice Merger")

            # Initial size/position (Hi‑DPI aware)
            try:
                scale = self.tk.call("tk", "scaling")
            except:
                scale = 1.0
            w, h = int(1100 / scale), int(800 / scale)
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 3
            self.geometry(f"{w}x{h}+{x}+{y}")

            # Window icon
            if PRIMARY_LOGO.is_file():
                try:
                    ic = ImageTk.PhotoImage(Image.open(PRIMARY_LOGO))
                    self.wm_iconphoto(True, ic)
                    self._icon = ic  # Keep a reference
                except Exception:
                    pass

            # State variables
            self.selected_files: List[str] = []
            self.q: queue.Queue[tuple[str, object]] = queue.Queue()
            self.processing = False
            self.output_folder = ctk.StringVar(value="")
            self.output_name = ctk.StringVar(value=DEFAULT_OUTPUT)

            # Build UI & drag‑and‑drop
            self._build_ui()
            self._setup_dnd()
            
            # Check for Ghostscript on startup
            if not check_ghostscript():
                self.after(100, lambda: messagebox.showwarning(
                    "Ghostscript Not Found",
                    "Ghostscript is required for PDF flattening.\n\n"
                    "Please install Ghostscript:\n"
                    "• Windows: https://www.ghostscript.com/download/gsdnld.html\n"
                    "• Mac: brew install ghostscript\n"
                    "• Linux: sudo apt-get install ghostscript"
                ))

        # ──────────────────────────────────────────────
        # UI construction helpers
        # ──────────────────────────────────────────────

        def _build_ui(self) -> None:
            outer = ctk.CTkFrame(self, fg_color="#1a1a1a")
            outer.pack(fill="both", expand=True)

            # Banner
            banner = ctk.CTkFrame(outer, fg_color="transparent")
            banner.pack(fill="x", pady=(6, 20))
            banner.grid_columnconfigure(1, weight=1)

            if CIRCLE_LOGO.is_file():
                try:
                    img = ctk.CTkImage(Image.open(CIRCLE_LOGO), size=(60, 60))
                    ctk.CTkLabel(banner, image=img, text="").grid(row=0, column=0, rowspan=2, padx=12)
                    self._logo = img  # Keep reference
                except Exception:
                    pass

            ctk.CTkLabel(
                banner,
                text="Invoice Merger",
                font=ctk.CTkFont(size=28, weight="bold"),
            ).grid(row=0, column=1, sticky="s")

            ctk.CTkLabel(
                banner,
                text="Merge Cover Sheet + Invoice → two‑page PDF",
                text_color="gray70",
            ).grid(row=1, column=1, sticky="n")

            # Main card
            card = ctk.CTkFrame(outer, corner_radius=10)
            card.pack(fill="both", expand=True, padx=24, pady=(0, 16))
            card.grid_columnconfigure(0, weight=1)
            # allow file list to expand while keeping output options visible
            card.grid_rowconfigure(3, weight=1)

            ctk.CTkLabel(
                card,
                text="Drag PDFs or folders:",
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="we", padx=20, pady=(20, 8))

            # Drag‑and‑drop zone
            self.dz = ctk.CTkFrame(
                card, height=100, corner_radius=10, border_width=2, border_color="gray40"
            )
            self.dz.grid(row=1, column=0, sticky="we", padx=20)
            self.dz.grid_propagate(False)

            inner = ctk.CTkFrame(self.dz, fg_color="transparent")
            inner.place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(inner, text="📄", font=ctk.CTkFont(size=34)).pack()
            ctk.CTkLabel(inner, text="Drag PDFs/folders here or click Browse", text_color="gray70").pack(
                pady=(4, 0)
            )

            # Browse buttons
            bb = ctk.CTkFrame(card, fg_color="transparent")
            bb.grid(row=2, column=0, sticky="we", padx=20, pady=8)
            bb.grid_columnconfigure((0, 1), weight=1)
            ctk.CTkButton(bb, text="Browse Files", command=self._browse_files).grid(
                row=0, column=0, sticky="we", padx=(0, 6)
            )
            ctk.CTkButton(bb, text="Browse Folder", command=self._browse_folder).grid(
                row=0, column=1, sticky="we", padx=(6, 0)
            )

            # File list
            self.list_frame = ctk.CTkScrollableFrame(card, height=150, corner_radius=8)
            self.list_frame.grid(row=3, column=0, sticky="nswe", padx=20)
            self._refresh_list()

            # Output options
            out_frm = ctk.CTkFrame(card, corner_radius=8, fg_color="#2a2a2a")
            out_frm.grid(row=4, column=0, sticky="we", padx=20, pady=(12, 8))
            out_frm.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                out_frm,
                text="Output Options",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(8, 0))

            # Folder
            ctk.CTkLabel(out_frm, text="Folder:").grid(
                row=1, column=0, sticky="w", padx=(14, 8), pady=(6, 6)
            )
            self.out_entry = ctk.CTkEntry(
                out_frm,
                textvariable=self.output_folder,
                placeholder_text="Select output folder",
            )
            self.out_entry.grid(row=1, column=1, sticky="we", padx=(0, 8))
            ctk.CTkButton(out_frm, text="…", width=28, command=self._choose_output_folder).grid(
                row=1, column=2, padx=(0, 14)
            )

            # File name
            ctk.CTkLabel(out_frm, text="File name:").grid(
                row=2, column=0, sticky="w", padx=(14, 8), pady=(0, 12)
            )
            self.out_name_entry = ctk.CTkEntry(
                out_frm,
                textvariable=self.output_name,
                placeholder_text="Merged file name",
            )
            self.out_name_entry.grid(row=2, column=1, sticky="we", padx=(0, 8), pady=(0, 12))
            ctk.CTkLabel(out_frm, text=".pdf").grid(row=2, column=2, padx=(0, 14))

            # Action buttons
            act = ctk.CTkFrame(card, fg_color="transparent")
            act.grid(row=5, column=0, sticky="we", padx=20, pady=(10, 22))
            act.grid_columnconfigure((0, 2), weight=1)

            self.clear_btn = ctk.CTkButton(
                act, text="Clear", fg_color="#cc7a00", hover_color="#b36a00", command=self._clear
            )
            self.clear_btn.grid(row=0, column=0, sticky="we", padx=(0, 8))

            self.start_btn = ctk.CTkButton(
                act,
                text="Begin Processing",
                fg_color="#1ba01b",
                hover_color="#158015",
                command=self._start,
            )
            self.start_btn.grid(row=0, column=2, sticky="we", padx=(8, 0))

            # Progress & status
            self.prog = ctk.CTkProgressBar(card, height=16)
            self.prog.grid(row=6, column=0, sticky="we", padx=20)
            self.prog.set(0)

            self.status = ctk.CTkLabel(card, text="Ready")
            self.status.grid(row=7, column=0, sticky="w", padx=22, pady=(4, 12))

            self.console = ctk.CTkTextbox(card, height=90, state="disabled", corner_radius=6)
            self.console.grid(row=8, column=0, sticky="we", padx=20, pady=(0, 14))
            self.console.grid_remove()
            self.status.bind(
                "<Button-1>",
                lambda e: self.console.grid_remove() if self.console.winfo_ismapped() else self.console.grid(),
            )

        def _setup_dnd(self):
            self.dz.drop_target_register(DND_FILES)
            self.dz.dnd_bind("<<Drop>>", self._on_drop)
            self.dz.bind("<Button-1>", lambda e: self._browse_files())

        # ──────────────────────────────────────────────
        # File/queue helpers
        # ──────────────────────────────────────────────

        def _on_drop(self, e):
            self._add_items(self.tk.splitlist(e.data))

        def _add_items(self, paths: List[str]) -> None:
            added = 0
            invalid = 0
            
            for p in paths:
                pp = Path(p)
                if pp.is_dir():
                    for pdf in pp.glob("*.pdf"):
                        if str(pdf) not in self.selected_files:
                            if is_valid_pdf(pdf):
                                self.selected_files.append(str(pdf))
                                added += 1
                            else:
                                invalid += 1
                elif pp.suffix.lower() == ".pdf" and str(pp) not in self.selected_files:
                    if is_valid_pdf(pp):
                        self.selected_files.append(str(pp))
                        added += 1
                    else:
                        invalid += 1

            if added > 0:
                self._refresh_list()
                self._log(f"➕ Added {added} PDF(s)")
            
            if invalid > 0:
                self._log(f"⚠️ Skipped {invalid} invalid PDF(s)")

        def _refresh_list(self) -> None:
            for w in self.list_frame.winfo_children():
                w.destroy()

            if not self.selected_files:
                ctk.CTkLabel(
                    self.list_frame, text="No PDFs selected", text_color="gray70"
                ).pack(pady=20)
                return

            for idx, fp in enumerate(self.selected_files):
                row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
                row.pack(fill="x", pady=2, padx=2)

                ctk.CTkLabel(
                    row,
                    text=Path(fp).name,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    anchor="w",
                ).pack(side="left", padx=(6, 4))

                trunc = fp if len(fp) <= 90 else f"…{fp[-87:]}"
                ctk.CTkLabel(
                    row,
                    text=trunc,
                    text_color="gray70",
                    font=ctk.CTkFont(size=10),
                    anchor="w",
                ).pack(side="left", fill="x", expand=True)

                ctk.CTkButton(
                    row,
                    text="×",
                    width=28,
                    height=28,
                    fg_color="#cc2020",
                    hover_color="#a51616",
                    command=lambda i=idx: self._remove_file(i),
                ).pack(side="right", padx=4)

        def _remove_file(self, idx: int) -> None:
            if 0 <= idx < len(self.selected_files):
                removed = self.selected_files.pop(idx)
                self._refresh_list()
                self._log(f"➖ Removed: {Path(removed).name}")

        def _browse_files(self) -> None:
            files = filedialog.askopenfilenames(
                title="Select PDF files",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            )
            if files:
                self._add_items(list(files))

        def _browse_folder(self) -> None:
            folder = filedialog.askdirectory(title="Select folder containing PDFs")
            if folder:
                self._add_items([folder])

        def _choose_output_folder(self) -> None:
            folder = filedialog.askdirectory(title="Select output folder")
            if folder:
                self.output_folder.set(folder)

        def _clear(self) -> None:
            self.selected_files.clear()
            self._refresh_list()
            self._log("🗑️ Cleared all files")

        # ──────────────────────────────────────────────
        # Processing
        # ──────────────────────────────────────────────

        def _start(self) -> None:
            if self.processing:
                return

            if len(self.selected_files) < 2:
                messagebox.showwarning(
                    "Not Enough PDFs",
                    "Please select Cover Sheet and Invoice PDFs to merge.",
                )
                return

            # Validate output name
            out_name = self.output_name.get().strip()
            if not out_name:
                messagebox.showerror("Invalid Name", "Please enter an output file name.")
                return

            # Determine output location
            out_folder = self.output_folder.get().strip()
            if not out_folder:
                out_folder = str(Path(self.selected_files[0]).parent)
                self.output_folder.set(out_folder)

            # Check if output folder exists
            if not Path(out_folder).exists():
                messagebox.showerror("Invalid Folder", "The selected output folder does not exist.")
                return

            # Start processing thread
            self.processing = True
            self._update_ui_state(False)
            threading.Thread(target=self._process_thread, daemon=True).start()

            # Start UI update loop
            self.after(50, self._check_queue)

        def _process_thread(self) -> None:
            try:
                self.q.put(("progress", 0.1))
                self.q.put(("status", "🔍 Analyzing PDFs..."))

                pdfs = [Path(f) for f in self.selected_files]
                pairs = pair_cover_invoices(pdfs)

                if not pairs:
                    self.q.put(
                        (
                            "error",
                            "No valid 'Cover Sheet' + 'Invoice' pairs found!",
                        )
                    )
                    return

                self.q.put(("log", f"📄 Found {len(pairs)} PDF pair(s) to merge"))

                # Process each pair
                out_folder = Path(self.output_folder.get())
                out_name = self.output_name.get().strip()
                if not out_name.endswith(".pdf"):
                    out_name += ".pdf"

                successful = 0
                failed = 0

                for i, (cover, invoice) in enumerate(pairs):
                    self.q.put(("progress", 0.2 + (i / len(pairs)) * 0.6))
                    self.q.put(("status", f"Processing {i+1}/{len(pairs)}: {invoice.name}"))

                    # Create temp file for flattened cover
                    temp_flat = out_folder / f"TEMP_FLAT_{cover.stem}_{i}.pdf"
                    temp_final = None
                    
                    try:
                        # Flatten cover sheet
                        self.q.put(("log", f"🔧 Flattening: {cover.name}"))
                        gs_flatten(cover, temp_flat)

                        # Determine output name
                        if len(pairs) == 1:
                            final_out = out_folder / out_name
                        else:
                            # Multiple pairs: use invoice name
                            final_out = out_folder / f"MERGED_{invoice.stem}.pdf"

                        # Check if output file already exists
                        if final_out.exists():
                            response = messagebox.askyesno(
                                "File Exists",
                                f"The file {final_out.name} already exists.\n\nOverwrite it?"
                            )
                            if not response:
                                self.q.put(("log", f"⏭️ Skipped: {final_out.name} (already exists)"))
                                continue

                        # Merge
                        self.q.put(("log", f"🔗 Merging with: {invoice.name}"))
                        merge_pdfs(temp_flat, invoice, final_out)

                        # Flatten the merged result
                        self.q.put(("log", f"🔧 Flattening final: {final_out.name}"))
                        temp_final = out_folder / f"TEMP_FINAL_{final_out.stem}_{i}.pdf"
                        gs_flatten(final_out, temp_final)
                        
                        # Replace with flattened version
                        if final_out.exists():
                            final_out.unlink()
                        temp_final.rename(final_out)

                        self.q.put(("log", f"✅ Created: {final_out.name}"))
                        successful += 1

                    except Exception as e:
                        self.q.put(("log", f"❌ Error processing {invoice.name}: {str(e)}"))
                        failed += 1
                        
                    finally:
                        # Cleanup temp files
                        for temp_file in [temp_flat, temp_final]:
                            if temp_file and temp_file.exists():
                                try:
                                    temp_file.unlink()
                                except:
                                    pass

                self.q.put(("progress", 1.0))
                
                if successful > 0:
                    status_msg = f"✅ Processed {successful} pair(s)"
                    if failed > 0:
                        status_msg += f", {failed} failed"
                    self.q.put(("status", status_msg))
                    self.q.put(("success", f"Successfully processed {successful} pair(s).\n\nOutput folder: {out_folder}"))
                else:
                    self.q.put(("status", "❌ Processing failed"))
                    self.q.put(("error", "Failed to process any PDF pairs. Check the console for errors."))

            except Exception as e:
                self.q.put(("error", f"Processing failed:\n{str(e)}"))

        def _check_queue(self) -> None:
            try:
                while True:
                    msg_type, data = self.q.get_nowait()
                    
                    if msg_type == "progress":
                        self.prog.set(data)
                    elif msg_type == "status":
                        self.status.configure(text=data)
                    elif msg_type == "log":
                        self._log(data)
                    elif msg_type == "success":
                        self._update_ui_state(True)
                        self.processing = False
                        messagebox.showinfo("Success", data)
                    elif msg_type == "error":
                        self._update_ui_state(True)
                        self.processing = False
                        messagebox.showerror("Error", data)
                        
            except queue.Empty:
                pass

            if self.processing:
                self.after(50, self._check_queue)

        def _update_ui_state(self, enabled: bool) -> None:
            state = "normal" if enabled else "disabled"
            self.start_btn.configure(state=state)
            self.clear_btn.configure(state=state)
            for widget in [self.out_entry, self.out_name_entry]:
                widget.configure(state=state)

        def _log(self, msg: str) -> None:
            self.console.configure(state="normal")
            self.console.insert("end", f"{msg}\n")
            self.console.see("end")
            self.console.configure(state="disabled")

# ────────────────────────────────────────────────────────────
# CLI fallback
# ────────────────────────────────────────────────────────────

def cli_main() -> None:
    """Command-line interface fallback."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Merge 'Cover Sheet' and 'Invoice' PDFs"
    )
    parser.add_argument(
        "pdfs",
        nargs="+",
        type=Path,
        help="PDF files to process",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path.cwd() / DEFAULT_OUTPUT,
        help=f"Output PDF path (default: {DEFAULT_OUTPUT})",
    )

    args = parser.parse_args()

    # Check Ghostscript
    if not check_ghostscript():
        print("❌ Ghostscript not found! Please install Ghostscript:")
        print("• Windows: https://www.ghostscript.com/download/gsdnld.html")
        print("• Mac: brew install ghostscript")
        print("• Linux: sudo apt-get install ghostscript")
        sys.exit(1)

    # Validate PDFs
    valid_pdfs = []
    for pdf in args.pdfs:
        if not pdf.exists():
            print(f"⚠️ File not found: {pdf}")
        elif not is_valid_pdf(pdf):
            print(f"⚠️ Invalid PDF: {pdf}")
        else:
            valid_pdfs.append(pdf)

    if len(valid_pdfs) < 2:
        print("❌ Need at least 2 valid PDFs!")
        sys.exit(1)

    # Pair PDFs
    pairs = pair_cover_invoices(valid_pdfs)
    if not pairs:
        print("❌ No valid 'Cover Sheet' + 'Invoice' pairs found!")
        sys.exit(1)

    print(f"📄 Found {len(pairs)} pair(s) to merge")

    try:
        # Process
        for i, (cover, invoice) in enumerate(pairs):
            temp_flat = args.output.parent / f"TEMP_FLAT_{cover.stem}_{i}.pdf"

            print(f"🔧 Flattening {cover.name}...")
            gs_flatten(cover, temp_flat)

            if len(pairs) == 1:
                out_file = args.output
                print(f"🔗 Merging with {invoice.name}...")
            else:
                out_file = args.output.parent / f"MERGED_{invoice.stem}.pdf"
                print(f"🔗 Merging {cover.name} + {invoice.name} → {out_file.name}")
            merge_pdfs(temp_flat, invoice, out_file)

            # Flatten the final output
            print(f"🔧 Flattening final output...")
            temp_final = out_file.parent / f"TEMP_FINAL_{out_file.stem}.pdf"
            gs_flatten(out_file, temp_final)
            out_file.unlink()
            temp_final.rename(out_file)

            print(f"✅ Created: {out_file}")

        # Cleanup
        if temp_flat.exists():
            temp_flat.unlink()
        print("✅ Done!")

    except Exception as e:
        print(f"❌ Error: {e}")
        # Cleanup on error
        if 'temp_flat' in locals() and temp_flat.exists():
            temp_flat.unlink()
        sys.exit(1)

# ────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────

def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        # CLI mode
        cli_main()
    else:
        # GUI mode
        if not GUI_AVAILABLE:
            print("GUI dependencies not available. Please install:")
            print("pip install customtkinter tkinterdnd2 pillow pypdf2")
            print("\nOr use CLI mode:")
            print(f"python {Path(__file__).name} <pdf1> <pdf2> ... [-o output.pdf]")
            sys.exit(1)
        
        try:
            app = InvoiceMergeGUI()
            app.mainloop()
        except Exception as e:
            print(f"GUI Error: {e}")
            print("\nFalling back to CLI mode...")
            print(f"Usage: python {Path(__file__).name} <pdf1> <pdf2> ...")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()