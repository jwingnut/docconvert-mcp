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


def convert_file(src: Path, dst: Path, fmt: str) -> dict:
    """Convert a single file to target format (in-process, for non-PDFs or sequential)."""
    fmt = fmt.lower()
    fmt = {"md": "markdown", "txt": "plain", "tex": "latex"}.get(fmt, fmt)

    try:
        if src.suffix.lower() == '.pdf':
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


def convert_pdf_subprocess(src: Path, dst: Path, fmt: str) -> dict:
    """Convert PDF in isolated subprocess (enables true parallelism)."""
    fmt = fmt.lower()
    fmt = {"md": "markdown", "txt": "plain", "tex": "latex"}.get(fmt, fmt)

    # Build inline Python code to run in subprocess
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
            timeout=600  # 10 min timeout per PDF
        )
        if result.returncode == 0:
            return {"success": True, "output": str(dst)}
        else:
            return {"success": False, "error": result.stderr.decode() or "Subprocess failed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout (10 min)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _convert_task(args: tuple) -> dict:
    """Worker function for parallel conversion (non-PDF)."""
    src_file, out_file, fmt, overwrite = args

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
    result = convert_file(src_file, out_file, fmt)
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
    src_file, out_file, fmt, overwrite = args

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
    result = convert_pdf_subprocess(src_file, out_file, fmt)
    return {
        "input": str(src_file),
        "input_format": src_file.suffix.lower(),
        "output": str(out_file) if result.get("success") else None,
        "success": result.get("success"),
        "skipped": False,
        "error": result.get("error")
    }


@mcp.tool
def convert(input: str, output: str, format: str, filter: str = None, recursive: bool = False, parallel: int = 1, overwrite: bool = True) -> dict:
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

    Returns:
        Conversion result with output path(s)

    Examples:
        # Single file
        convert("/path/to/doc.pdf", "/path/to/doc.odt", "odt")

        # Directory - convert all supported files to ODT
        convert("/path/to/mixed_docs/", "/path/to/output/", "odt", recursive=True)

        # Directory - parallel PDF conversion (4 workers) - requires sufficient CPU/RAM
        convert("/path/to/docs/", "/path/to/md_output/", "markdown", filter="pdf", recursive=True, parallel=4)

        # Directory - parallel conversion for mixed files (4 workers)
        convert("/path/to/docs/", "/path/to/output/", "html", recursive=True, parallel=4)

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

        result = convert_file(src, dst, fmt)
        result["skipped"] = False
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
        tasks.append((f, out_file, fmt, overwrite))

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
        "note": "PDF input uses pdf2docx then pandoc. All other conversions use pandoc directly."
    }


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


if __name__ == "__main__":
    mcp.run()
