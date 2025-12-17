# DocConvert MCP Server

FastMCP server for universal document format conversion. Convert PDFs, Word docs, HTML, Markdown, LaTeX, and more to any output format.

## Features

- **Universal conversion** - Convert between 20+ document formats
- **PDF support** - Uses pdf2docx for accurate PDF extraction, then pandoc
- **OCR support** - Extract text from scanned PDFs with layout preservation
- **GROBID integration** - Extract metadata and references from academic PDFs
- **Batch processing** - Convert entire directories with mixed formats
- **Parallel processing** - Subprocess isolation for true PDF parallelism
- **Recursive mode** - Process nested folder structures
- **Format filtering** - Convert only specific file types (e.g., just PDFs)

## Architecture

```
Claude Code
    │
    └── DocConvert MCP Server (this)
            │
            ├── pdf2docx (PDF → DOCX extraction)
            ├── PyMuPDF (OCR with layout preservation)
            ├── GROBID (metadata + references extraction)
            │
            └── pandoc (all other conversions)
```

## Supported Formats

### Input Formats
`pdf`, `docx`, `odt`, `html`, `md`, `tex`, `latex`, `rst`, `epub`, `rtf`, `txt`, `org`, `mediawiki`, `textile`, `asciidoc`

### Output Formats
`odt`, `docx`, `html`, `markdown`, `latex`, `pdf`, `epub`, `rst`, `asciidoc`, `rtf`, `txt`, `org`, `mediawiki`

## Installation

### Prerequisites

```bash
# Install pandoc
sudo apt install pandoc
```

### Setup

```bash
git clone https://github.com/jwingnut/docconvert-mcp.git
cd docconvert-mcp
uv venv
source .venv/bin/activate
uv pip install fastmcp pdf2docx
```

## MCP Client Configuration

<details>
  <summary><strong>Claude Code CLI</strong></summary>

Create or edit `.mcp.json` in your project directory (or a parent directory for broader scope):

```json
{
  "mcpServers": {
    "docconvert": {
      "command": "/path/to/docconvert-mcp/.venv/bin/python",
      "args": ["/path/to/docconvert-mcp/pdf2odt_mcp_server.py"]
    }
  }
}
```

Then enable the server in `.claude/settings.local.json`:

```json
{
  "enabledMcpjsonServers": ["docconvert"]
}
```

</details>

<details>
  <summary><strong>Claude Desktop</strong></summary>

Add to your `claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "docconvert": {
      "command": "/path/to/docconvert-mcp/.venv/bin/python",
      "args": ["/path/to/docconvert-mcp/pdf2odt_mcp_server.py"]
    }
  }
}
```

</details>

<details>
  <summary><strong>Codex CLI</strong></summary>

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.docconvert]
command = "/path/to/docconvert-mcp/.venv/bin/python"
args = ["/path/to/docconvert-mcp/pdf2odt_mcp_server.py"]
startup_timeout_sec = 30
```

</details>

<details>
  <summary><strong>Cursor</strong></summary>

Add to your Cursor MCP settings (Settings → MCP → Add Server):

```json
{
  "mcpServers": {
    "docconvert": {
      "command": "/path/to/docconvert-mcp/.venv/bin/python",
      "args": ["/path/to/docconvert-mcp/pdf2odt_mcp_server.py"]
    }
  }
}
```

</details>

<details>
  <summary><strong>Windsurf</strong></summary>

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "docconvert": {
      "command": "/path/to/docconvert-mcp/.venv/bin/python",
      "args": ["/path/to/docconvert-mcp/pdf2odt_mcp_server.py"]
    }
  }
}
```

</details>

<details>
  <summary><strong>Cline / Claude Dev</strong></summary>

Add to your Cline MCP settings:

```json
{
  "mcpServers": {
    "docconvert": {
      "command": "/path/to/docconvert-mcp/.venv/bin/python",
      "args": ["/path/to/docconvert-mcp/pdf2odt_mcp_server.py"]
    }
  }
}
```

</details>

<details>
  <summary><strong>Continue IDE Extension</strong></summary>

Add to your Continue configuration:

```json
{
  "mcpServers": {
    "docconvert": {
      "command": "/path/to/docconvert-mcp/.venv/bin/python",
      "args": ["/path/to/docconvert-mcp/pdf2odt_mcp_server.py"]
    }
  }
}
```

</details>

<details>
  <summary><strong>Alternative: Using fastmcp run</strong></summary>

You can also run via the `fastmcp` CLI with `--no-banner` to suppress output:

```json
{
  "mcpServers": {
    "docconvert": {
      "command": "/path/to/docconvert-mcp/.venv/bin/fastmcp",
      "args": ["run", "--no-banner", "/path/to/docconvert-mcp/pdf2odt_mcp_server.py"]
    }
  }
}
```

</details>

## Tools

### `convert`

Convert document(s) to a target format.

```python
# Single file: PDF to Markdown
convert(
    input="/path/to/document.pdf",
    output="/path/to/document.md",
    format="markdown"
)

# Single file: PDF to ODT
convert(
    input="/path/to/paper.pdf",
    output="/path/to/paper.odt",
    format="odt"
)

# Directory: Convert all supported files to markdown
convert(
    input="/path/to/docs/",
    output="/path/to/output/",
    format="markdown",
    recursive=True
)

# Directory: Only convert PDFs to ODT
convert(
    input="/path/to/mixed_docs/",
    output="/path/to/odt_output/",
    format="odt",
    filter="pdf",
    recursive=True
)
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `input` | string | Input file or directory path |
| `output` | string | Output file or directory path |
| `format` | string | Target format (odt, docx, markdown, html, etc.) |
| `filter` | string | Optional - only convert files with this extension |
| `recursive` | bool | If True, process subdirectories |
| `parallel` | int | Number of parallel workers (default 1 = sequential, max 16) |
| `overwrite` | bool | If True (default), overwrite existing files. If False, skip existing. |

**Parallel Processing:**

Parallel processing is available for all file types. PDF files use subprocess isolation to bypass pdf2docx's internal locking and achieve true parallelism. Requires adequate CPU and RAM.

```python
# Parallel PDF conversion (4 workers)
convert(
    input="/path/to/pdfs/",
    output="/path/to/output/",
    format="markdown",
    filter="pdf",
    recursive=True,
    parallel=4  # Each PDF runs in isolated subprocess
)

# Response shows parallel PDF info:
# {"total": 10, "converted": 10, "pdf_files": 10, "pdf_parallel": true, "pdf_workers": 4}

# Convert markdown files in parallel (4 workers)
convert(
    input="/path/to/markdown_docs/",
    output="/path/to/output/",
    format="html",
    filter="md",
    recursive=True,
    parallel=4
)

# Mixed formats: all parallel
convert(
    input="/path/to/mixed_docs/",  # Contains PDFs and markdown
    output="/path/to/output/",
    format="html",
    recursive=True,
    parallel=4
)

# Response shows breakdown:
# {"total": 50, "converted": 50, "pdf_files": 10, "pdf_parallel": true, "pdf_workers": 4, "parallel_workers": 4, "parallel_files": 40}
```

**Note:** Parallel PDF processing requires sufficient CPU and RAM. On resource-constrained systems, use `parallel=1` (default) for reliable sequential processing.

**Skip Existing Files:**

Use `overwrite=False` to skip files that already exist (useful for resuming interrupted batches):

```python
# Resume an interrupted batch - only convert files not yet done
convert(
    input="/path/to/docs/",
    output="/path/to/output/",
    format="markdown",
    recursive=True,
    overwrite=False  # Skip existing output files
)

# Response includes skipped count:
# {"total": 100, "converted": 25, "skipped": 75, "failed": 0}
```

### `formats`

List all supported input and output formats.

```python
formats()
# Returns:
# {
#   "input_formats": ["asciidoc", "docx", "epub", "htm", "html", ...],
#   "output_formats": ["asciidoc", "docx", "epub", "html", "latex", ...],
#   "note": "PDF input uses pdf2docx then pandoc..."
# }
```

### `list_convertible`

List convertible files in a path, grouped by format.

```python
list_convertible("/path/to/docs/", recursive=True)
# Returns:
# {
#   "success": True,
#   "count": 15,
#   "by_format": {
#     ".pdf": ["file1.pdf", "file2.pdf"],
#     ".docx": ["report.docx"],
#     ".md": ["notes.md", "readme.md"]
#   }
# }
```

## Use Cases

### Academic Writing

Convert journal guidelines and example papers for easy reference:

```python
# Convert journal author guidelines
convert(
    input="/path/to/author_guidelines.pdf",
    output="/path/to/guidelines.md",
    format="markdown"
)

# Convert example papers to study structure
convert(
    input="/path/to/example_paper.pdf",
    output="/path/to/example.md",
    format="markdown"
)
```

### Document Migration

Batch convert legacy documents:

```python
# Convert all Word docs to ODT
convert(
    input="/path/to/word_docs/",
    output="/path/to/odt_docs/",
    format="odt",
    filter="docx",
    recursive=True
)
```

### Content Extraction

Extract text from PDFs for analysis:

```python
# Convert PDFs to plain text
convert(
    input="/path/to/pdfs/",
    output="/path/to/text/",
    format="txt",
    filter="pdf"
)
```

### Web Publishing

Convert documents to HTML:

```python
# Markdown to HTML
convert(
    input="/path/to/docs/",
    output="/path/to/html/",
    format="html",
    filter="md",
    recursive=True
)
```

## Integration

Works alongside other MCP servers:

- **[LibreOffice MCP](https://github.com/jwingnut/libreoffice-mcp-ubuntu)** - Edit converted documents
- **[Zotero MCP](https://github.com/jwingnut/zotero-mcp-ubuntu)** - Add citations to converted content

### Workflow Example

```python
# 1. Convert journal guidelines
convert(input="guidelines.pdf", output="guidelines.md", format="markdown")

# 2. Read guidelines
Read("guidelines.md")

# 3. Create document in LibreOffice
document(action="create", doc_type="writer")

# 4. Write content following guidelines
text(action="insert", content="...")

# 5. Add citations from Zotero
search_zotero("topic")
text(action="insert", content="{  | (Author, 2020) |  |  |zu:LIB:KEY}")

# 6. Save
save(action="save", file_path="paper.odt")
```

## Technical Notes

### PDF Conversion

PDFs are converted in two stages:
1. **pdf2docx** extracts content to DOCX (preserves layout, tables, images)
2. **pandoc** converts DOCX to target format

This produces better results than direct PDF parsing for most documents.

### Other Formats

All non-PDF conversions use pandoc directly, which handles:
- Document structure (headings, lists, tables)
- Basic formatting
- Cross-references
- Citations (in some formats)

### Parallel PDF Processing

PDF parallelism uses subprocess isolation: each PDF conversion runs in a completely separate Python process. This bypasses pdf2docx's internal locking that prevents thread-based parallelism.

- Each subprocess: ~100-200MB RAM + CPU usage
- 4 parallel workers: ~400-800MB RAM, 4 CPU cores
- 8 parallel workers: ~800MB-1.6GB RAM, 8 CPU cores

### OCR for Scanned PDFs

**Standard OCR (`ocr=True`)** - Preserves tables and layout (recommended):
```python
# Best quality - preserves tables and structure
convert(
    input="/path/to/scanned.pdf",
    output="/path/to/output.md",
    format="markdown",
    ocr=True
)

# Batch OCR conversion
convert(
    input="/path/to/scanned_docs/",
    output="/path/to/output/",
    format="markdown",
    filter="pdf",
    ocr=True,
    recursive=True
)
```

**Fast OCR (`ocr=True, ocr_fast=True`)** - Simpler, loses layout:
```python
convert(
    input="/path/to/scanned.pdf",
    output="/path/to/output.txt",
    format="txt",
    ocr=True,
    ocr_fast=True
)
```

**Standalone OCR** - Create searchable PDF:
```python
ocr_document("/path/to/scanned.pdf", "/path/to/searchable.pdf")
```

**OCR Requirements:**
```bash
# Standard OCR (recommended)
pip install pymupdf4llm

# Fast OCR (optional)
pip install ocrmypdf
sudo apt install tesseract-ocr
```

### GROBID for Academic PDFs

Extract structured metadata and references from scholarly documents using GROBID:

```python
# Extract metadata (title, authors, abstract, DOI, etc.)
extract_metadata("/path/to/paper.pdf")
# Returns: {title, authors, abstract, keywords, date, doi, affiliations}

# Extract bibliography/references
extract_references("/path/to/paper.pdf")
# Returns: [{title, authors, year, journal, volume, pages, doi}, ...]

# Extract full document structure
extract_fulltext("/path/to/paper.pdf")
# Returns: metadata + all references

# Save as TEI XML
extract_fulltext("/path/to/paper.pdf", "/path/to/paper.tei.xml")
```

**GROBID Requirements:**
```bash
# Start GROBID server (Docker)
docker run -d --name grobid -p 8070:8070 lfoppiano/grobid:0.8.0

# Install client
pip install grobid-client-python

# Optional: Set custom server URL
export GROBID_SERVER=http://your-server:8070
```

### Limitations

- Complex PDF layouts may not convert perfectly
- Some formatting may be lost in conversion
- Parallel PDF processing requires adequate system resources
- OCR quality depends on scan quality and Tesseract's capabilities
- GROBID requires a running server (local or remote)

## Files

```
pdf2odt-mcp/
├── pdf2odt_mcp_server.py  # MCP server
├── .venv/                  # Virtual environment
├── .gitignore
└── README.md
```

## License

MIT
