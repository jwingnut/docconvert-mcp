#!/usr/bin/env python3
"""
Document Converter MCP Server - Universal document format conversion

Converts documents between any formats using pdf2docx (for PDFs) and pandoc.
Handles mixed input formats in directories - converts everything to one output format.

Supported formats: odt, docx, html, markdown, latex, epub, rst, pdf, rtf, txt, and more.

Usage:
    fastmcp run pdf2odt_mcp_server.py
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastmcp import FastMCP
from pdf2docx import Converter

# Optional: pymupdf4llm for better OCR with layout preservation
try:
    import pymupdf4llm
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# Optional: GROBID for metadata and reference extraction
try:
    from grobid_client.grobid_client import GrobidClient
    from bs4 import BeautifulSoup
    HAS_GROBID = True
except ImportError:
    HAS_GROBID = False

# Default GROBID server URL (can be overridden)
GROBID_SERVER = os.environ.get("GROBID_SERVER", "http://localhost:8070")

mcp = FastMCP("docconvert")

# Supported input extensions
INPUT_EXTENSIONS = {
    '.pdf', '.docx', '.odt', '.html', '.htm', '.md', '.markdown',
    '.tex', '.latex', '.rst', '.epub', '.rtf', '.txt', '.org',
    '.mediawiki', '.textile', '.asciidoc', '.adoc'
}

# Output formats
OUTPUT_FORMATS = [
    "odt", "docx", "html", "markdown", "md", "latex", "tex", "pdf",
    "epub", "rst", "asciidoc", "rtf", "txt", "org", "mediawiki"
]

EXT_MAP = {
    "markdown": ".md", "md": ".md", "gfm": ".md",
    "latex": ".tex", "tex": ".tex",
    "plain": ".txt", "txt": ".txt",
    "html5": ".html", "asciidoc": ".adoc"
}


def ocr_pdf(src: Path, dst: Path = None) -> dict:
    """
    Run OCR on a PDF to make it searchable.

    Uses ocrmypdf which:
    - Detects if PDF already has text (skips OCR if so)
    - Adds searchable text layer to scanned pages
    - Preserves original quality

    Args:
        src: Input PDF path
        dst: Output PDF path (if None, creates temp file)

    Returns:
        dict with success status and output path
    """
    try:
        if dst is None:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                dst = Path(tmp.name)

        result = subprocess.run(
            ['ocrmypdf', '--skip-text', str(src), str(dst)],
            capture_output=True,
            timeout=600  # 10 min timeout
        )

        if result.returncode == 0:
            return {"success": True, "output": str(dst)}
        elif result.returncode == 6:
            # Exit code 6 = PDF already has text, copy original
            shutil.copy(str(src), str(dst))
            return {"success": True, "output": str(dst), "skipped": "already has text"}
        else:
            return {"success": False, "error": result.stderr.decode() or "OCR failed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "OCR timeout (10 min)"}
    except FileNotFoundError:
        return {"success": False, "error": "ocrmypdf not installed. Run: pip install ocrmypdf && sudo apt install tesseract-ocr"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def ocr_with_layout(src: Path, dst: Path, fmt: str) -> dict:
    """
    OCR a PDF using PyMuPDF with layout preservation.

    Better for documents with tables and complex layouts.
    Uses pymupdf4llm for markdown output, fitz for other formats.

    Args:
        src: Input PDF path
        dst: Output file path
        fmt: Target format (markdown, html, txt, etc.)

    Returns:
        dict with success status and output path
    """
    if not HAS_PYMUPDF:
        return {"success": False, "error": "pymupdf4llm not installed. Run: pip install pymupdf4llm"}

    try:
        if fmt in ("markdown", "md"):
            # Use pymupdf4llm for best markdown output with tables
            md_text = pymupdf4llm.to_markdown(str(src))
            dst.write_text(md_text)
        else:
            # Use fitz OCR then extract text
            doc = fitz.open(str(src))
            all_text = []
            for page in doc:
                tp = page.get_textpage_ocr(language='eng', dpi=300, full=True)
                if fmt == "html":
                    all_text.append(page.get_text('html', textpage=tp))
                else:
                    all_text.append(page.get_text('text', textpage=tp))
            doc.close()

            content = '\n'.join(all_text)

            if fmt == "html":
                dst.write_text(content)
            elif fmt in ("plain", "txt"):
                dst.write_text(content)
            else:
                # For other formats, write as txt then convert with pandoc
                with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as tmp:
                    tmp.write(content)
                    txt_path = tmp.name
                subprocess.run(['pandoc', txt_path, '-o', str(dst)], check=True, capture_output=True)
                os.unlink(txt_path)

        return {"success": True, "output": str(dst)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def convert_file(src: Path, dst: Path, fmt: str, ocr: bool = False, ocr_fast: bool = False) -> dict:
    """Convert a single file to target format (in-process, for non-PDFs or sequential)."""
    fmt = fmt.lower()
    fmt = {"md": "markdown", "txt": "plain", "tex": "latex"}.get(fmt, fmt)
    ocr_tmp = None

    try:
        if src.suffix.lower() == '.pdf':
            # OCR with layout preservation (PyMuPDF) - default OCR mode
            if ocr and not ocr_fast:
                return ocr_with_layout(src, dst, fmt)

            # Fast OCR (ocrmypdf + pdftotext) - simpler but loses layout
            if ocr_fast:
                ocr_result = ocr_pdf(src)
                if not ocr_result.get("success"):
                    return ocr_result
                ocr_tmp = ocr_result["output"]

                # Extract text from OCR'd PDF using pdftotext, then convert with pandoc
                with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as txt_tmp:
                    txt_path = txt_tmp.name
                subprocess.run(['pdftotext', '-layout', ocr_tmp, txt_path], check=True, capture_output=True)

                if fmt in ("plain", "txt"):
                    shutil.move(txt_path, str(dst))
                else:
                    subprocess.run(['pandoc', txt_path, '-o', str(dst)], check=True, capture_output=True)
                    os.unlink(txt_path)
            else:
                # Normal PDF: use pdf2docx for better layout preservation
                with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                    docx_tmp = tmp.name

                cv = Converter(str(src))
                cv.convert(docx_tmp)
                cv.close()

                if fmt == "docx":
                    shutil.move(docx_tmp, str(dst))
                else:
                    subprocess.run(['pandoc', docx_tmp, '-o', str(dst)], check=True, capture_output=True)
                    os.unlink(docx_tmp)
        else:
            subprocess.run(['pandoc', str(src), '-o', str(dst)], check=True, capture_output=True)

        return {"success": True, "output": str(dst)}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": e.stderr.decode() if e.stderr else str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # Clean up OCR temp file
        if ocr_tmp and os.path.exists(ocr_tmp):
            os.unlink(ocr_tmp)


def convert_pdf_subprocess(src: Path, dst: Path, fmt: str, ocr: bool = False) -> dict:
    """Convert PDF in isolated subprocess (enables true parallelism)."""
    fmt = fmt.lower()
    fmt = {"md": "markdown", "txt": "plain", "tex": "latex"}.get(fmt, fmt)

    # Build inline Python code to run in subprocess
    if ocr:
        # OCR path: ocrmypdf -> pdftotext -> pandoc
        txt_final = fmt in ("plain", "txt")
        code = f'''
import sys, os, subprocess, tempfile, shutil
ocr_tmp = None
txt_tmp = None
try:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        ocr_tmp = tmp.name
    ocr_result = subprocess.run(["ocrmypdf", "--skip-text", "{src}", ocr_tmp], capture_output=True)
    if ocr_result.returncode == 6:  # Already has text
        shutil.copy("{src}", ocr_tmp)
    elif ocr_result.returncode != 0:
        raise Exception(f"OCR failed: {{ocr_result.stderr.decode()}}")
    # Extract text with pdftotext
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        txt_tmp = tmp.name
    subprocess.run(["pdftotext", "-layout", ocr_tmp, txt_tmp], check=True, capture_output=True)
    {"shutil.move(txt_tmp, '" + str(dst) + "'); txt_tmp = None" if txt_final else f'subprocess.run(["pandoc", txt_tmp, "-o", "{dst}"], check=True, capture_output=True)'}
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
finally:
    if ocr_tmp and os.path.exists(ocr_tmp):
        os.unlink(ocr_tmp)
    if txt_tmp and os.path.exists(txt_tmp):
        os.unlink(txt_tmp)
'''
    else:
        # Normal path: pdf2docx -> pandoc (better layout preservation)
        code = f'''
import sys, os, tempfile, subprocess, logging
logging.getLogger("pdf2docx").setLevel(logging.ERROR)
from pdf2docx import Converter
try:
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        docx_tmp = tmp.name
    cv = Converter("{src}")
    cv.convert(docx_tmp)
    cv.close()
    {"import shutil; shutil.move(docx_tmp, '" + str(dst) + "')" if fmt == "docx" else f'subprocess.run(["pandoc", docx_tmp, "-o", "{dst}"], check=True, capture_output=True); os.unlink(docx_tmp)'}
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
'''
    try:
        result = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True,
            timeout=900  # 15 min timeout (OCR adds time)
        )
        if result.returncode == 0:
            return {"success": True, "output": str(dst)}
        else:
            return {"success": False, "error": result.stderr.decode() or "Subprocess failed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout (15 min)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _convert_task(args: tuple) -> dict:
    """Worker function for parallel conversion (non-PDF)."""
    src_file, out_file, fmt, overwrite, ocr, ocr_fast = args

    # Skip if output exists and overwrite is False
    if not overwrite and out_file.exists():
        return {
            "input": str(src_file),
            "input_format": src_file.suffix.lower(),
            "output": str(out_file),
            "success": True,
            "skipped": True
        }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    result = convert_file(src_file, out_file, fmt, ocr=ocr, ocr_fast=ocr_fast)
    return {
        "input": str(src_file),
        "input_format": src_file.suffix.lower(),
        "output": str(out_file) if result.get("success") else None,
        "success": result.get("success"),
        "skipped": False,
        "error": result.get("error")
    }


def _convert_pdf_task(args: tuple) -> dict:
    """Worker function for parallel PDF conversion using subprocess isolation."""
    src_file, out_file, fmt, overwrite, ocr, ocr_fast = args

    # Skip if output exists and overwrite is False
    if not overwrite and out_file.exists():
        return {
            "input": str(src_file),
            "input_format": src_file.suffix.lower(),
            "output": str(out_file),
            "success": True,
            "skipped": True
        }

    out_file.parent.mkdir(parents=True, exist_ok=True)

    # For OCR with layout (default), use in-process PyMuPDF
    if ocr and not ocr_fast:
        result = ocr_with_layout(src_file, out_file, fmt)
    else:
        result = convert_pdf_subprocess(src_file, out_file, fmt, ocr=ocr_fast)
    return {
        "input": str(src_file),
        "input_format": src_file.suffix.lower(),
        "output": str(out_file) if result.get("success") else None,
        "success": result.get("success"),
        "skipped": False,
        "error": result.get("error")
    }


@mcp.tool
def convert(input: str, output: str, format: str, filter: str = None, recursive: bool = False, parallel: int = 1, overwrite: bool = True, ocr: bool = False, ocr_fast: bool = False) -> dict:
    """
    Convert document(s) to a single output format.

    Handles mixed input formats - PDFs, DOCX, HTML, Markdown, etc. all get converted
    to the specified output format. Directory structure is preserved in output.

    Args:
        input: Input file or directory path
        output: Output file or directory path
        format: Target format for ALL outputs (odt, docx, html, markdown, latex, epub, rst, pdf, rtf, txt, etc.)
        filter: Optional - only convert files with this extension (e.g., 'pdf'). If omitted, converts all supported formats.
        recursive: If True, traverse subdirectories and convert all files found
        parallel: Number of parallel workers (default 1 = sequential). For PDFs, uses subprocess isolation
                  to bypass pdf2docx internal locking and achieve true parallelism. Requires adequate CPU/RAM.
        overwrite: If True (default), overwrite existing output files. If False, skip files that already exist.
        ocr: If True, run OCR on scanned PDFs using PyMuPDF. Preserves tables and layout.
             Requires: pip install pymupdf4llm
        ocr_fast: If True (with ocr=True), use fast OCR mode (ocrmypdf + pdftotext). Faster but loses layout.
                  Requires: pip install ocrmypdf, apt install tesseract-ocr

    Returns:
        Conversion result with output path(s)

    Examples:
        # Single file
        convert("/path/to/doc.pdf", "/path/to/doc.odt", "odt")

        # Scanned PDF with OCR (preserves tables and layout)
        convert("/path/to/scanned.pdf", "/path/to/scanned.md", "markdown", ocr=True)

        # Scanned PDF with fast OCR (simpler, loses layout)
        convert("/path/to/scanned.pdf", "/path/to/scanned.txt", "txt", ocr=True, ocr_fast=True)

        # Batch OCR conversion
        convert("/path/to/scanned_docs/", "/path/to/output/", "markdown", filter="pdf", ocr=True, recursive=True)

        # Directory - parallel PDF conversion (4 workers) - requires sufficient CPU/RAM
        convert("/path/to/docs/", "/path/to/md_output/", "markdown", filter="pdf", recursive=True, parallel=4)

        # Skip existing files (resume interrupted batch)
        convert("/path/to/docs/", "/path/to/output/", "odt", recursive=True, overwrite=False)
    """
    src = Path(input)
    dst = Path(output)
    fmt = format.lower()
    ext = EXT_MAP.get(fmt, f".{fmt}")

    if not src.exists():
        return {"success": False, "error": f"Input not found: {src}"}

    # Single file conversion
    if src.is_file():
        if not dst.suffix or str(output).endswith('/'):
            dst.mkdir(parents=True, exist_ok=True)
            dst = dst / src.with_suffix(ext).name
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)

        # Check overwrite for single file
        if not overwrite and dst.exists():
            return {"success": True, "output": str(dst), "skipped": True, "message": "Output file exists, skipped"}

        result = convert_file(src, dst, fmt, ocr=ocr, ocr_fast=ocr_fast)
        result["skipped"] = False
        if ocr and src.suffix.lower() == '.pdf':
            result["ocr"] = "fast" if ocr_fast else True
        return result

    # Directory conversion
    if not src.is_dir():
        return {"success": False, "error": f"Input is neither file nor directory: {src}"}

    dst.mkdir(parents=True, exist_ok=True)

    # Find files to convert
    if filter:
        # Only specific extension
        filter_ext = f".{filter.lstrip('.')}"
        if recursive:
            files = [f for f in src.rglob('*') if f.is_file() and f.suffix.lower() == filter_ext]
        else:
            files = [f for f in src.glob('*') if f.is_file() and f.suffix.lower() == filter_ext]
    else:
        # All supported formats (mixed input)
        if recursive:
            files = [f for f in src.rglob('*') if f.is_file() and f.suffix.lower() in INPUT_EXTENSIONS]
        else:
            files = [f for f in src.glob('*') if f.is_file() and f.suffix.lower() in INPUT_EXTENSIONS]

    if not files:
        return {"success": True, "message": "No supported files found", "converted": 0, "failed": 0}

    # Prepare conversion tasks
    tasks = []
    for f in sorted(files):
        rel_path = f.relative_to(src)
        out_file = dst / rel_path.with_suffix(ext)
        tasks.append((f, out_file, fmt, overwrite, ocr, ocr_fast))

    results = []
    converted = 0
    failed = 0
    skipped = 0

    # Split tasks into PDF and non-PDF
    pdf_tasks = [t for t in tasks if t[0].suffix.lower() == '.pdf']
    other_tasks = [t for t in tasks if t[0].suffix.lower() != '.pdf']

    num_workers = max(1, min(parallel, 16))  # Clamp between 1-16

    # Process PDFs - parallel with subprocess isolation, or sequential
    if num_workers > 1 and len(pdf_tasks) > 1:
        # Parallel PDF processing using subprocess isolation (bypasses pdf2docx locking)
        try:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {executor.submit(_convert_pdf_task, task): task for task in pdf_tasks}
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=660)  # 11 min (slightly > subprocess timeout)
                        results.append(result)
                        if result.get("skipped"):
                            skipped += 1
                        elif result.get("success"):
                            converted += 1
                        else:
                            failed += 1
                    except Exception as e:
                        task = futures[future]
                        results.append({
                            "input": str(task[0]),
                            "input_format": task[0].suffix.lower(),
                            "output": None,
                            "success": False,
                            "error": f"Task failed: {str(e)}"
                        })
                        failed += 1
        except Exception as e:
            # Fallback to sequential if parallel fails
            for task in pdf_tasks:
                result = _convert_task(task)
                results.append(result)
                if result.get("skipped"):
                    skipped += 1
                elif result.get("success"):
                    converted += 1
                else:
                    failed += 1
    else:
        # Sequential PDF processing (default, or single file)
        for task in pdf_tasks:
            result = _convert_task(task)
            results.append(result)
            if result.get("skipped"):
                skipped += 1
            elif result.get("success"):
                converted += 1
            else:
                failed += 1

    # Process non-PDFs in parallel if requested
    if num_workers > 1 and len(other_tasks) > 1:
        try:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {executor.submit(_convert_task, task): task for task in other_tasks}
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=300)
                        results.append(result)
                        if result.get("skipped"):
                            skipped += 1
                        elif result.get("success"):
                            converted += 1
                        else:
                            failed += 1
                    except Exception as e:
                        task = futures[future]
                        results.append({
                            "input": str(task[0]),
                            "input_format": task[0].suffix.lower(),
                            "output": None,
                            "success": False,
                            "error": f"Task failed: {str(e)}"
                        })
                        failed += 1
        except Exception as e:
            # Fallback to sequential if parallel fails
            for task in other_tasks:
                result = _convert_task(task)
                results.append(result)
                if result.get("skipped"):
                    skipped += 1
                elif result.get("success"):
                    converted += 1
                else:
                    failed += 1
    else:
        # Sequential processing for non-PDFs
        for task in other_tasks:
            result = _convert_task(task)
            results.append(result)
            if result.get("skipped"):
                skipped += 1
            elif result.get("success"):
                converted += 1
            else:
                failed += 1

    # Sort results by input path for consistent output
    results.sort(key=lambda x: x["input"])

    response = {
        "success": True,
        "total": len(files),
        "converted": converted,
        "failed": failed,
        "output_format": fmt,
        "results": results
    }

    if skipped > 0:
        response["skipped"] = skipped
    if len(pdf_tasks) > 0:
        response["pdf_files"] = len(pdf_tasks)
        if ocr:
            response["ocr"] = "fast" if ocr_fast else True
        if num_workers > 1 and len(pdf_tasks) > 1:
            response["pdf_parallel"] = True
            response["pdf_workers"] = num_workers
    if num_workers > 1 and len(other_tasks) > 1:
        response["parallel_workers"] = num_workers
        response["parallel_files"] = len(other_tasks)

    return response


@mcp.tool
def formats() -> dict:
    """List supported input and output formats."""
    return {
        "input_formats": sorted([e.lstrip('.') for e in INPUT_EXTENSIONS]),
        "output_formats": OUTPUT_FORMATS,
        "note": "PDF input uses pdf2docx then pandoc. All other conversions use pandoc directly.",
        "ocr": "Use ocr=True with convert() or ocr_document() for scanned PDFs. Requires tesseract-ocr."
    }


@mcp.tool
def ocr_document(input: str, output: str = None) -> dict:
    """
    Run OCR on a scanned PDF to make it searchable.

    Uses Tesseract OCR via ocrmypdf. Automatically detects if PDF already has text
    and skips OCR if so. Output is a searchable PDF that can then be converted
    to other formats.

    Args:
        input: Input PDF file path
        output: Output PDF path. If not specified, creates file with _ocr suffix.

    Returns:
        dict with success status and output path

    Examples:
        # OCR a scanned document
        ocr_document("/path/to/scanned.pdf", "/path/to/searchable.pdf")

        # Auto-name output (creates scanned_ocr.pdf)
        ocr_document("/path/to/scanned.pdf")

    Requires:
        pip install ocrmypdf
        sudo apt install tesseract-ocr
    """
    src = Path(input)

    if not src.exists():
        return {"success": False, "error": f"Input not found: {src}"}

    if src.suffix.lower() != '.pdf':
        return {"success": False, "error": "Input must be a PDF file"}

    if output:
        dst = Path(output)
    else:
        dst = src.with_stem(src.stem + "_ocr")

    dst.parent.mkdir(parents=True, exist_ok=True)

    result = ocr_pdf(src, dst)
    return result


@mcp.tool
def list_convertible(path: str, recursive: bool = False) -> dict:
    """
    List all convertible files in a path.

    Args:
        path: File or directory path
        recursive: If True, search subdirectories

    Returns:
        List of convertible files grouped by format
    """
    p = Path(path)

    if not p.exists():
        return {"success": False, "error": f"Path not found: {p}"}

    if p.is_file():
        if p.suffix.lower() in INPUT_EXTENSIONS:
            return {"success": True, "count": 1, "files": {p.suffix.lower(): [str(p)]}}
        else:
            return {"success": False, "error": f"Not a supported format: {p.suffix}"}

    # Directory
    if recursive:
        files = [f for f in p.rglob('*') if f.is_file() and f.suffix.lower() in INPUT_EXTENSIONS]
    else:
        files = [f for f in p.glob('*') if f.is_file() and f.suffix.lower() in INPUT_EXTENSIONS]

    # Group by format
    by_format = {}
    for f in sorted(files):
        ext = f.suffix.lower()
        if ext not in by_format:
            by_format[ext] = []
        by_format[ext].append(str(f))

    return {
        "success": True,
        "count": len(files),
        "by_format": by_format
    }


def _parse_tei_metadata(tei_xml: str) -> dict:
    """Parse TEI XML from GROBID to extract metadata."""
    soup = BeautifulSoup(tei_xml, 'xml')

    metadata = {}

    # Title
    title_elem = soup.find('title', {'type': 'main'})
    if title_elem:
        metadata['title'] = title_elem.get_text(strip=True)

    # Authors
    authors = []
    for author in soup.find_all('author'):
        author_info = {}
        persname = author.find('persName')
        if persname:
            forename = persname.find('forename')
            surname = persname.find('surname')
            if forename:
                author_info['first_name'] = forename.get_text(strip=True)
            if surname:
                author_info['last_name'] = surname.get_text(strip=True)
            if forename and surname:
                author_info['name'] = f"{forename.get_text(strip=True)} {surname.get_text(strip=True)}"

        # Affiliation
        affiliation = author.find('affiliation')
        if affiliation:
            org = affiliation.find('orgName')
            if org:
                author_info['affiliation'] = org.get_text(strip=True)

        # Email
        email = author.find('email')
        if email:
            author_info['email'] = email.get_text(strip=True)

        if author_info:
            authors.append(author_info)

    if authors:
        metadata['authors'] = authors

    # Abstract
    abstract = soup.find('abstract')
    if abstract:
        # Get all paragraphs in abstract
        paragraphs = abstract.find_all('p')
        if paragraphs:
            metadata['abstract'] = ' '.join(p.get_text(strip=True) for p in paragraphs)
        else:
            metadata['abstract'] = abstract.get_text(strip=True)

    # Keywords
    keywords = soup.find('keywords')
    if keywords:
        terms = keywords.find_all('term')
        if terms:
            metadata['keywords'] = [t.get_text(strip=True) for t in terms]

    # Publication date
    date = soup.find('date', {'type': 'published'})
    if date:
        metadata['date'] = date.get('when', date.get_text(strip=True))

    # DOI
    idno = soup.find('idno', {'type': 'DOI'})
    if idno:
        metadata['doi'] = idno.get_text(strip=True)

    return metadata


def _parse_tei_references(tei_xml: str) -> list:
    """Parse TEI XML from GROBID to extract references."""
    soup = BeautifulSoup(tei_xml, 'xml')

    references = []
    for bibl in soup.find_all('biblStruct'):
        ref = {}

        # Title
        title = bibl.find('title', {'level': 'a'}) or bibl.find('title')
        if title:
            ref['title'] = title.get_text(strip=True)

        # Authors
        authors = []
        for author in bibl.find_all('author'):
            persname = author.find('persName')
            if persname:
                forename = persname.find('forename')
                surname = persname.find('surname')
                if forename and surname:
                    authors.append(f"{forename.get_text(strip=True)} {surname.get_text(strip=True)}")
                elif surname:
                    authors.append(surname.get_text(strip=True))
        if authors:
            ref['authors'] = authors

        # Year
        date = bibl.find('date')
        if date:
            ref['year'] = date.get('when', date.get_text(strip=True))[:4] if date.get('when') else date.get_text(strip=True)

        # Journal/Source
        journal = bibl.find('title', {'level': 'j'})
        if journal:
            ref['journal'] = journal.get_text(strip=True)

        # Volume, issue, pages
        vol = bibl.find('biblScope', {'unit': 'volume'})
        if vol:
            ref['volume'] = vol.get_text(strip=True)

        issue = bibl.find('biblScope', {'unit': 'issue'})
        if issue:
            ref['issue'] = issue.get_text(strip=True)

        pages = bibl.find('biblScope', {'unit': 'page'})
        if pages:
            ref['pages'] = pages.get('from', '') + ('-' + pages.get('to', '') if pages.get('to') else '')
            if not ref['pages']:
                ref['pages'] = pages.get_text(strip=True)

        # DOI
        doi = bibl.find('idno', {'type': 'DOI'})
        if doi:
            ref['doi'] = doi.get_text(strip=True)

        if ref:
            references.append(ref)

    return references


@mcp.tool
def extract_metadata(input: str, grobid_server: str = None) -> dict:
    """
    Extract metadata from a PDF using GROBID.

    Extracts title, authors, abstract, keywords, date, DOI, and affiliations
    from academic/scholarly PDFs.

    Args:
        input: Input PDF file path
        grobid_server: GROBID server URL (default: http://localhost:8070 or GROBID_SERVER env var)

    Returns:
        dict with extracted metadata

    Examples:
        extract_metadata("/path/to/paper.pdf")
        extract_metadata("/path/to/paper.pdf", grobid_server="http://grobid.example.com:8070")

    Requires:
        - GROBID server running (docker run -p 8070:8070 lfoppiano/grobid:0.8.0)
        - pip install grobid-client-python
    """
    if not HAS_GROBID:
        return {"success": False, "error": "grobid-client-python not installed. Run: pip install grobid-client-python"}

    src = Path(input)
    if not src.exists():
        return {"success": False, "error": f"Input not found: {src}"}

    if src.suffix.lower() != '.pdf':
        return {"success": False, "error": "Input must be a PDF file"}

    server = grobid_server or GROBID_SERVER

    try:
        client = GrobidClient(grobid_server=server, check_server=True)
    except Exception as e:
        return {"success": False, "error": f"Cannot connect to GROBID server at {server}: {str(e)}"}

    try:
        # Process header (metadata)
        status, tei_xml = client.process_pdf(
            service="processHeaderDocument",
            pdf_file=str(src),
            generateIDs=False,
            consolidate_header=True,
            consolidate_citations=False,
            include_raw_citations=False,
            include_raw_affiliations=True,
            tei_coordinates=False,
            segment_sentences=False
        )

        if status != 200:
            return {"success": False, "error": f"GROBID returned status {status}"}

        metadata = _parse_tei_metadata(tei_xml)
        metadata['success'] = True
        metadata['source'] = str(src)
        return metadata

    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool
def extract_references(input: str, grobid_server: str = None) -> dict:
    """
    Extract bibliographic references from a PDF using GROBID.

    Parses the reference section of academic PDFs and returns structured
    citation data including authors, title, journal, year, DOI, etc.

    Args:
        input: Input PDF file path
        grobid_server: GROBID server URL (default: http://localhost:8070 or GROBID_SERVER env var)

    Returns:
        dict with list of extracted references

    Examples:
        extract_references("/path/to/paper.pdf")

    Requires:
        - GROBID server running (docker run -p 8070:8070 lfoppiano/grobid:0.8.0)
        - pip install grobid-client-python
    """
    if not HAS_GROBID:
        return {"success": False, "error": "grobid-client-python not installed. Run: pip install grobid-client-python"}

    src = Path(input)
    if not src.exists():
        return {"success": False, "error": f"Input not found: {src}"}

    if src.suffix.lower() != '.pdf':
        return {"success": False, "error": "Input must be a PDF file"}

    server = grobid_server or GROBID_SERVER

    try:
        client = GrobidClient(grobid_server=server, check_server=True)
    except Exception as e:
        return {"success": False, "error": f"Cannot connect to GROBID server at {server}: {str(e)}"}

    try:
        # Process references
        status, tei_xml = client.process_pdf(
            service="processReferences",
            pdf_file=str(src),
            generateIDs=False,
            consolidate_header=False,
            consolidate_citations=True,
            include_raw_citations=True,
            include_raw_affiliations=False,
            tei_coordinates=False,
            segment_sentences=False
        )

        if status != 200:
            return {"success": False, "error": f"GROBID returned status {status}"}

        references = _parse_tei_references(tei_xml)
        return {
            "success": True,
            "source": str(src),
            "count": len(references),
            "references": references
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool
def extract_fulltext(input: str, output: str = None, grobid_server: str = None) -> dict:
    """
    Extract full structured text from a PDF using GROBID.

    Returns the complete document structure including metadata, sections,
    paragraphs, figures, tables, and references as TEI XML or parsed content.

    Args:
        input: Input PDF file path
        output: Optional output file path for TEI XML. If not specified, returns parsed content.
        grobid_server: GROBID server URL (default: http://localhost:8070 or GROBID_SERVER env var)

    Returns:
        dict with structured document content or path to TEI XML file

    Examples:
        # Get parsed content
        extract_fulltext("/path/to/paper.pdf")

        # Save TEI XML
        extract_fulltext("/path/to/paper.pdf", "/path/to/paper.tei.xml")

    Requires:
        - GROBID server running (docker run -p 8070:8070 lfoppiano/grobid:0.8.0)
        - pip install grobid-client-python
    """
    if not HAS_GROBID:
        return {"success": False, "error": "grobid-client-python not installed. Run: pip install grobid-client-python"}

    src = Path(input)
    if not src.exists():
        return {"success": False, "error": f"Input not found: {src}"}

    if src.suffix.lower() != '.pdf':
        return {"success": False, "error": "Input must be a PDF file"}

    server = grobid_server or GROBID_SERVER

    try:
        client = GrobidClient(grobid_server=server, check_server=True)
    except Exception as e:
        return {"success": False, "error": f"Cannot connect to GROBID server at {server}: {str(e)}"}

    try:
        # Process full document
        status, tei_xml = client.process_pdf(
            service="processFulltextDocument",
            pdf_file=str(src),
            generateIDs=True,
            consolidate_header=True,
            consolidate_citations=True,
            include_raw_citations=True,
            include_raw_affiliations=True,
            tei_coordinates=False,
            segment_sentences=True
        )

        if status != 200:
            return {"success": False, "error": f"GROBID returned status {status}"}

        # If output path specified, save TEI XML
        if output:
            dst = Path(output)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(tei_xml)
            return {
                "success": True,
                "source": str(src),
                "output": str(dst),
                "format": "tei-xml"
            }

        # Otherwise return parsed content
        metadata = _parse_tei_metadata(tei_xml)
        references = _parse_tei_references(tei_xml)

        return {
            "success": True,
            "source": str(src),
            "metadata": metadata,
            "references": references,
            "reference_count": len(references)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    import logging
    # Redirect all logging to stderr to keep stdout clean for MCP JSON-RPC
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    mcp.run(show_banner=False)
