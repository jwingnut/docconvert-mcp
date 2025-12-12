# DocConvert MCP Server

FastMCP server for universal document format conversion. Convert PDFs, Word docs, HTML, Markdown, LaTeX, and more to any output format.

## Features

- **Universal conversion** - Convert between 20+ document formats
- **PDF support** - Uses pdf2docx for accurate PDF extraction, then pandoc
- **Batch processing** - Convert entire directories with mixed formats
- **Parallel processing** - Optional multiprocessing for faster batch jobs (bypasses Python GIL)
- **Recursive mode** - Process nested folder structures
- **Format filtering** - Convert only specific file types (e.g., just PDFs)

## Architecture

```
Claude Code
    │
    └── DocConvert MCP Server (this)
            │
            ├── pdf2docx (PDF → DOCX extraction)
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

# Install pdf2docx
pip install pdf2docx
```

### Setup

```bash
cd /path/to/pdf2odt-mcp
uv venv
source .venv/bin/activate
uv pip install fastmcp pdf2docx
```

### Configure Claude Code

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "docconvert": {
      "command": "/path/to/pdf2odt-mcp/.venv/bin/fastmcp",
      "args": ["run", "/path/to/pdf2odt-mcp/pdf2odt_mcp_server.py"]
    }
  }
}
```

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

For faster batch conversion, use the `parallel` parameter:

```python
# Convert 50 PDFs using 4 parallel workers (~4x faster)
convert(
    input="/path/to/many_pdfs/",
    output="/path/to/output/",
    format="markdown",
    filter="pdf",
    recursive=True,
    parallel=4
)

# Recommended settings:
# - parallel=1: Default, sequential (safest)
# - parallel=2-4: Good for most systems
# - parallel=4-8: For systems with many CPU cores
# - parallel=8-16: Power users with fast storage
```

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

### Limitations

- Complex PDF layouts may not convert perfectly
- Some formatting may be lost in conversion
- Scanned PDFs (images) require OCR first (not included)

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
