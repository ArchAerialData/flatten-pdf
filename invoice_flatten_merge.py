#!/usr/bin/env python3
"""invoice_flatten_merge.py

Flatten a filled‑out WHCRWA "6.0 Vendor Invoice Cover Sheet" PDF and merge it
with the related Arch Aerial / GFT invoice so you end up with a single,
*completely* flattened two‑page PDF that is ready to email.

---------------------------------------------------------------------
Usage
---------------------------------------------------------------------
1. **Drag & drop** a folder containing the two PDFs onto the script *or*
   run from the command line:

       python invoice_flatten_merge.py "C:\Path\To\Folder"

2. The folder must contain at least two PDFs –‑ one that represents the
   vendor form (its file‑name typically contains words like "Vendor",
   "6.0", or "Cover") and one regular invoice PDF.

3. The script will:
   • Flatten the vendor‑form PDF (burning in every form field).
   • Merge the flattened vendor form followed by the GFT invoice.
   • Re‑flatten the merged two‑page document for good measure.
   • Write **FINAL_MERGED_INVOICE.pdf** back into the same folder.

---------------------------------------------------------------------
Dependencies
---------------------------------------------------------------------
• Python ≥ 3.8  
• Ghostscript executable on your PATH   
    – `gswin64c` on Windows (installed with the official GS package)  
    – `gs` on macOS / Linux  
• PyPDF2 3.x – install with `pip install pypdf2`

---------------------------------------------------------------------
Notes
---------------------------------------------------------------------
• The Ghostscript `pdfwrite` device automatically flattens and embeds form
  data. Passing the `-dPrinted` switch guarantees AcroForm widgets are
  discarded.
• If you need different naming logic (e.g. more than one pair of PDFs),
  tweak the `VENDOR_KEYWORDS` list or add additional pattern matching in
  `identify_vendor_pdf()`.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List

from PyPDF2 import PdfReader, PdfWriter

# ------------------------------------------------------------------
# CONFIGURATION -----------------------------------------------------
# ------------------------------------------------------------------
# Words that must appear in the file name (case‑insensitive) to treat
# a PDF as the vendor cover sheet.
VENDOR_KEYWORDS: List[str] = [
    "vendor", "cover", "6.0", "whcrwa"
]

# Name of the final output PDF
FINAL_NAME = "FINAL_MERGED_INVOICE.pdf"


# ------------------------------------------------------------------
# Ghostscript helper ------------------------------------------------
# ------------------------------------------------------------------

def gs_flatten(in_pdf: Path, out_pdf: Path) -> None:
    """Flatten *in_pdf* using Ghostscript and write *out_pdf*.

    Raises `subprocess.CalledProcessError` if Ghostscript exits with
    non‑zero status.
    """
    gs_exe = "gswin64c" if os.name == "nt" else "gs"
    cmd = [
        gs_exe,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.6",
        "-dPDFSETTINGS=/printer",     # reasonable compromise (300 dpi)
        "-dPrinted",                  # drop AcroForm widgets, keep ink
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={out_pdf}",
        str(in_pdf),
    ]
    subprocess.run(cmd, check=True)


# ------------------------------------------------------------------
# PDF helpers -------------------------------------------------------
# ------------------------------------------------------------------

def merge_pdfs(first: Path, second: Path, out_pdf: Path) -> None:
    """Concatenate *first* and *second* into *out_pdf*."""
    writer = PdfWriter()
    for pdf in (first, second):
        reader = PdfReader(str(pdf))
        for page in reader.pages:
            writer.add_page(page)
    with out_pdf.open("wb") as fh:
        writer.write(fh)


def identify_vendor_pdf(pdfs: List[Path]) -> Path:
    """Return the Path for the vendor invoice based on `VENDOR_KEYWORDS`."""
    for pdf in pdfs:
        name = pdf.name.lower()
        if any(word in name for word in VENDOR_KEYWORDS):
            return pdf
    # Fallback – just pick the first one
    return pdfs[0]


# ------------------------------------------------------------------
# Main workflow -----------------------------------------------------
# ------------------------------------------------------------------

def process_folder(folder: Path) -> None:
    pdfs = sorted(folder.glob("*.pdf"))
    if len(pdfs) < 2:
        print("[!] Need at least two PDFs in the folder", file=sys.stderr)
        return

    vendor_pdf = identify_vendor_pdf(pdfs)
    gft_pdf = next((p for p in pdfs if p != vendor_pdf), None)

    if gft_pdf is None:
        print("[!] Could not find the GFT invoice PDF", file=sys.stderr)
        return

    print(f"Vendor PDF : {vendor_pdf.name}")
    print(f"GFT PDF    : {gft_pdf.name}")

    # 1) Flatten vendor form ---------------------------------------
    vendor_flat = vendor_pdf.with_name(vendor_pdf.stem + "_flat.pdf")
    print("Flattening vendor form…", end=" ")
    gs_flatten(vendor_pdf, vendor_flat)
    print("done")

    # 2) Merge ------------------------------------------------------
    temp_merged = folder / "_merged_temp.pdf"
    print("Merging PDFs…", end=" ")
    merge_pdfs(vendor_flat, gft_pdf, temp_merged)
    print("done")

    # 3) Flatten merged result -------------------------------------
    final_pdf = folder / FINAL_NAME
    print("Flattening merged file…", end=" ")
    gs_flatten(temp_merged, final_pdf)
    print("done")

    # 4) Cleanup temp files ----------------------------------------
    vendor_flat.unlink(missing_ok=True)
    temp_merged.unlink(missing_ok=True)

    print(f"\n[✓] Created {final_pdf.relative_to(folder)}")


# ------------------------------------------------------------------
# Entry‑point -------------------------------------------------------
# ------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Drag a folder onto this script or run: python invoice_flatten_merge.py <folder>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1]).expanduser().resolve()
    if not target.is_dir():
        print("[!] Provided path is not a folder", file=sys.stderr)
        sys.exit(1)

    try:
        process_folder(target)
    except subprocess.CalledProcessError as e:
        print("[!] Ghostscript failed:", e, file=sys.stderr)
        sys.exit(e.returncode)
