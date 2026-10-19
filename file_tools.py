"""Read-only file tools the model can call: list, search and read files
inside the folders listed under [files] in models.toml, and nowhere else.

PDF pages that are mostly images (like lecture slides) are also read by a
vision model (OCR), so the text and diagrams in the images become searchable.
OCR results are cached in .ocr_cache, so each page is only read once.
"""
import hashlib
import io
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pypdfium2
from pypdf import PdfReader

log = logging.getLogger('typegpt')
logging.getLogger('pypdf').setLevel(logging.ERROR)  # Font warnings on some PDFs are harmless noise

TEXT_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.csv', '.tsv', '.json', '.yaml', '.yml', '.toml', '.xml',
    '.html', '.htm', '.rtf', '.tex', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.h',
    '.go', '.rs', '.rb', '.sh', '.sql', '.css', '.ini', '.log',
}
READABLE_EXTENSIONS = TEXT_EXTENSIONS | {'.pdf'}
CHUNK_CHARS = 4000        # Text files are split into "pages" of this size
MAX_READ_CHARS = 24000    # Most text one read_file call returns
MAX_LIST_ENTRIES = 400
MAX_SEARCH_RESULTS = 40
MAX_FILE_BYTES = 50_000_000
OCR_TEXT_LIMIT = 1500     # PDF pages with images and less text than this get OCR
OCR_RENDER_SCALE = 1.5    # 1.5x a 720pt-wide slide is about 1080px
OCR_WORKERS = 6
OCR_LABEL = '[read from the page image]'


class FileAccessError(Exception):
    pass


class FileLibrary:
    """The allowed folders, with a cache of extracted text."""

    def __init__(self, folders, ocr=None, ocr_cache_dir=None, ocr_model=''):
        self.roots = {}  # Display name -> resolved folder
        for folder in folders:
            path = Path(folder).expanduser().resolve()
            if not path.is_dir():
                log.warning('files | folder not found, skipping: %s', path)
                continue
            name = path.name
            while name in self.roots:
                name += '_'
            self.roots[name] = path
        self._cache = {}  # Resolved path -> (mtime, pages, indexes of pages that need OCR)
        self.ocr = ocr  # Function: JPEG bytes -> text, or None to skip OCR
        self.ocr_cache_dir = Path(ocr_cache_dir) if ocr_cache_dir else None
        self.ocr_model = ocr_model
        self._ocr_lock = threading.Lock()     # One writer for the cache files
        self._render_lock = threading.Lock()  # PDFium isn't thread-safe
        self._hashes = {}  # (path, mtime) -> content hash, the OCR cache key

    def __bool__(self):
        return bool(self.roots)

    def describe(self):
        return ', '.join(f'{name} ({path})' for name, path in self.roots.items())

    # Paths -----------------------------------------------------------------

    def resolve(self, display_path):
        """Turns 'soci369/slides/x.pdf' into a real path, refusing anything outside the roots."""
        display_path = (display_path or '').strip().strip('/')
        if not display_path:
            raise FileAccessError(f'Give a path starting with one of: {", ".join(self.roots)}')
        root_name, _, rest = display_path.partition('/')
        if root_name not in self.roots:
            raise FileAccessError(f'"{root_name}" is not an allowed folder. Allowed: {", ".join(self.roots)}')
        root = self.roots[root_name]
        path = (root / rest).resolve()  # Follows symlinks and ../ before the check
        if path != root and not path.is_relative_to(root):
            raise FileAccessError('That path is outside the allowed folders')
        if not path.exists():
            raise FileAccessError(f'No such file or folder: {display_path}')
        return path

    def display(self, path):
        for name, root in self.roots.items():
            if path == root or path.is_relative_to(root):
                rel = path.relative_to(root).as_posix()
                return name if rel == '.' else f'{name}/{rel}'
        raise FileAccessError('That path is outside the allowed folders')

    def files_under(self, folder):
        for path in sorted(folder.rglob('*')):
            if any(part.startswith('.') for part in path.relative_to(folder).parts):
                continue  # Hidden files and folders
            resolved = path.resolve()
            if not any(resolved == root or resolved.is_relative_to(root) for root in self.roots.values()):
                continue  # Symlink pointing outside the allowed folders
            if path.is_file():
                yield path

    # Text extraction -------------------------------------------------------

    def pages(self, path, ocr_now=False):
        """The file's text as a list of pages (PDF pages, or chunks of a text file).

        Pages that are mostly images include their OCR text once it's cached.
        ocr_now=True reads any of this file's missing pages first (used by read_file).
        """
        path = path.resolve()
        mtime = path.stat().st_mtime
        cached = self._cache.get(path)
        if not cached or cached[0] != mtime:
            cached = (mtime, *self._extract(path))
            self._cache[path] = cached
        _, pages, needs_ocr = cached
        if not needs_ocr or not self.ocr:
            return pages

        ocr_texts = self._load_ocr(path)
        missing = [i for i in needs_ocr if str(i + 1) not in ocr_texts]
        if ocr_now and missing:
            ocr_texts.update(self._run_ocr(path, missing))
        return [combine(text, ocr_texts.get(str(i + 1))) for i, text in enumerate(pages)]

    def _extract(self, path):
        if path.suffix.lower() not in READABLE_EXTENSIONS:
            raise FileAccessError(f'Can\'t read {path.suffix or "this"} files. Readable: PDF and text files')
        if path.stat().st_size > MAX_FILE_BYTES:
            raise FileAccessError('File is too large to read')

        if path.suffix.lower() != '.pdf':
            text = path.read_text(errors='replace')
            return [text[i:i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)] or [''], []

        pages, needs_ocr = [], []
        for i, page in enumerate(PdfReader(path).pages):
            text = (page.extract_text() or '').strip()
            pages.append(text)
            if len(text) < OCR_TEXT_LIMIT:
                try:
                    has_images = bool(page.images)
                except Exception:
                    has_images = not text  # Can't tell; OCR only if there's no text at all
                if has_images:
                    needs_ocr.append(i)
        return pages, needs_ocr

    # OCR -------------------------------------------------------------------

    def _ocr_cache_file(self, path):
        key = (path, path.stat().st_mtime)
        if key not in self._hashes:
            self._hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()[:24]
        return self.ocr_cache_dir / f'{self._hashes[key]}.json'

    def _load_ocr(self, path):
        if not self.ocr_cache_dir:
            return {}
        cache_file = self._ocr_cache_file(path)
        try:
            return json.loads(cache_file.read_text())['pages']
        except (FileNotFoundError, ValueError, KeyError):
            return {}

    def _run_ocr(self, path, page_indexes):
        """Reads the given pages' images with the OCR model; returns {page number: text}."""
        started = time.monotonic()
        images = {}
        with self._render_lock:
            pdf = pypdfium2.PdfDocument(str(path))
            try:
                for i in page_indexes:
                    image = pdf[i].render(scale=OCR_RENDER_SCALE).to_pil().convert('RGB')
                    buffer = io.BytesIO()
                    image.save(buffer, 'JPEG', quality=85)
                    images[i] = buffer.getvalue()
            finally:
                pdf.close()

        def read(i):
            try:
                return i, self.ocr(images[i])
            except Exception as e:
                log.warning('files | OCR failed for %s p.%d: %s', self.display(path), i + 1, e)
                return i, None

        results = {}
        with ThreadPoolExecutor(OCR_WORKERS) as pool:
            for i, text in pool.map(read, page_indexes):
                if text:
                    results[str(i + 1)] = text

        if results and self.ocr_cache_dir:
            with self._ocr_lock:
                self.ocr_cache_dir.mkdir(exist_ok=True)
                cache_file = self._ocr_cache_file(path)
                saved = self._load_ocr(path)
                saved.update(results)
                cache_file.write_text(json.dumps(
                    {'file': self.display(path), 'model': self.ocr_model, 'pages': saved}, indent=1))
        log.info('files | OCR %s | %d/%d pages read in %.1fs', self.display(path), len(results),
                 len(page_indexes), time.monotonic() - started)
        return results

    def index_ocr(self):
        """OCRs every image-heavy PDF page that isn't cached yet. Run in the background at startup."""
        if not self.ocr:
            return
        started = time.monotonic()
        files = cached = read = 0
        for root in self.roots.values():
            for path in self.files_under(root):
                if path.suffix.lower() != '.pdf':
                    continue
                try:
                    path = path.resolve()
                    self.pages(path)  # Fills the extraction cache
                    needs_ocr = self._cache[path][2]
                    if not needs_ocr:
                        continue
                    files += 1
                    done = self._load_ocr(path)
                    missing = [i for i in needs_ocr if str(i + 1) not in done]
                    cached += len(needs_ocr) - len(missing)
                    if missing:
                        read += len(self._run_ocr(path, missing))
                except Exception:
                    log.warning('files | OCR indexing failed for %s', path, exc_info=True)
        log.info('files | OCR index ready | files=%d pages_read=%d pages_already_cached=%d time=%.1fs',
                 files, read, cached, time.monotonic() - started)

    # Tools -----------------------------------------------------------------

    def list_files(self, path=None):
        folders = [self.resolve(path)] if path else list(self.roots.values())
        lines = []
        for folder in folders:
            if folder.is_file():
                folder = folder.parent
            for file in self.files_under(folder):
                readable = file.suffix.lower() in READABLE_EXTENSIONS
                size_kb = file.stat().st_size / 1024
                lines.append(f'{self.display(file)}  ({size_kb:.0f} KB{"" if readable else ", not readable"})')
                if len(lines) >= MAX_LIST_ENTRIES:
                    lines.append(f'... more files not shown; list a subfolder')
                    return '\n'.join(lines)
        return '\n'.join(lines) or 'No files found.'

    def search_files(self, query, path=None):
        terms = [t for t in re.split(r'\s+', (query or '').lower()) if t]
        if not terms:
            raise FileAccessError('Give a search query')
        folders = [self.resolve(path)] if path else list(self.roots.values())
        files = [f for folder in folders
                 for f in ([folder] if folder.is_file() else self.files_under(folder))
                 if f.suffix.lower() in READABLE_EXTENSIONS]

        exact, partial = [], []
        for file in files:
            try:
                pages = self.pages(file)  # Uses OCR text that's already cached
            except Exception as e:
                log.warning('files | could not read %s: %s', file, e)
                continue
            is_pdf = file.suffix.lower() == '.pdf'
            for number, page in enumerate(pages, 1):
                for line in page.splitlines():
                    lower = line.lower()
                    hits = sum(term in lower for term in terms)
                    if not hits:
                        continue
                    where = f'{self.display(file)} {"p." if is_pdf else "part "}{number}'
                    result = (hits, f'{where}: {line.strip()[:300]}')
                    (exact if hits == len(terms) else partial).append(result)

        partial.sort(key=lambda r: -r[0])
        results = [r for _, r in exact] + [r for _, r in partial]
        if not results:
            return f'No matches for "{query}". Try other words, or list_files and read_file.'
        shown = results[:MAX_SEARCH_RESULTS]
        more = f'\n... {len(results) - len(shown)} more matches; search more specifically' if len(results) > len(shown) else ''
        return '\n'.join(shown) + more

    def read_file(self, path, start_page=1, end_page=None):
        file = self.resolve(path)
        if file.is_dir():
            raise FileAccessError('That is a folder; use list_files')
        pages = self.pages(file, ocr_now=True)
        unit = 'page' if file.suffix.lower() == '.pdf' else 'part'
        start = max(1, int(start_page or 1))
        end = min(len(pages), int(end_page or len(pages)))
        if start > len(pages):
            raise FileAccessError(f'{path} has only {len(pages)} {unit}s')

        out, used = [], 0
        for number in range(start, end + 1):
            text = pages[number - 1] or '[no text on this page, probably an image]'
            if used + len(text) > MAX_READ_CHARS and out:
                end = number - 1
                break
            out.append(f'[{unit} {number}]\n{text}')
            used += len(text)
        header = f'{self.display(file)} ({unit}s {start}-{end} of {len(pages)})'
        if end < len(pages):
            header += f'. To continue, read_file with start_page={end + 1}'
        return header + '\n\n' + '\n\n'.join(out)

    def call(self, name, arguments):
        """Runs one tool call from the model. Errors come back as text for the model to see."""
        try:
            args = json.loads(arguments or '{}')
            if name == 'list_files':
                return self.list_files(args.get('path'))
            if name == 'search_files':
                return self.search_files(args.get('query'), args.get('path'))
            if name == 'read_file':
                return self.read_file(args.get('path'), args.get('start_page', 1), args.get('end_page'))
            return f'Unknown tool {name}'
        except FileAccessError as e:
            return f'Error: {e}'
        except json.JSONDecodeError:
            return 'Error: the tool arguments were not valid JSON'
        except Exception as e:
            log.warning('files | tool %s failed', name, exc_info=True)
            return f'Error: {type(e).__name__}: {e}'


def combine(text, ocr_text):
    """A page's extracted text plus what OCR read from its image."""
    if not ocr_text:
        return text
    if len(text.strip()) < 20:
        return f'{OCR_LABEL}\n{ocr_text}'
    return f'{text}\n\n{OCR_LABEL}\n{ocr_text}'


# Tool definitions in the OpenAI Chat Completions format (DeepSeek, OpenRouter)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List the files in the user's allowed folders (or one subfolder), with sizes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional folder to list, e.g. 'soci369/slides'. Omit to list everything."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search the text of every file (PDFs and text files) for words. Returns matching lines with file and page. Lines with all the words come first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "One or more words to look for, e.g. 'repressive hypothesis'."},
                    "path": {"type": "string", "description": "Optional folder or file to search within."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file's text. PDFs are read by page; text files by part. Long files are returned in sections; continue with start_page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path as shown by list_files, e.g. 'soci369/pages/EXAM1_INFO.txt'."},
                    "start_page": {"type": "integer", "description": "First page (or part) to read. Default 1."},
                    "end_page": {"type": "integer", "description": "Last page (or part) to read. Default: as much as fits."},
                },
                "required": ["path"],
            },
        },
    },
]


def tools_instructions(library):
    return (
        "You can read the user's own files with the tools list_files, search_files and read_file. "
        f"They can reach only these folders: {library.describe()}. "
        "Use them whenever the answer might be in the user's files, such as course notes, slides, readings, "
        "transcripts or a syllabus. Search first, then read the relevant pages. Base your answer on the files, "
        "and say which file and page the information comes from, in plain text, like (Class 4 slides, p. 3). "
        "If the files don't cover it, say so before answering from general knowledge. "
        "Do not write any text until you have finished using the tools."
    )
