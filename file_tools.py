"""Read-only file tools the model can call: list, search and read files
inside the folders listed under [files] in models.toml, and nowhere else.
"""
import json
import logging
import re
from pathlib import Path

from pypdf import PdfReader

log = logging.getLogger('typegpt')

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


class FileAccessError(Exception):
    pass


class FileLibrary:
    """The allowed folders, with a cache of extracted text."""

    def __init__(self, folders):
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
        self._cache = {}  # Resolved path -> (mtime, pages)

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

    def pages(self, path):
        """The file's text as a list of pages (PDF pages, or chunks of a text file)."""
        path = path.resolve()
        mtime = path.stat().st_mtime
        cached = self._cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]

        if path.suffix.lower() not in READABLE_EXTENSIONS:
            raise FileAccessError(f'Can\'t read {path.suffix or "this"} files. Readable: PDF and text files')
        if path.stat().st_size > MAX_FILE_BYTES:
            raise FileAccessError('File is too large to read')

        if path.suffix.lower() == '.pdf':
            pages = [(page.extract_text() or '').strip() for page in PdfReader(path).pages]
        else:
            text = path.read_text(errors='replace')
            pages = [text[i:i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)] or ['']
        self._cache[path] = (mtime, pages)
        return pages

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
                pages = self.pages(file)
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
        pages = self.pages(file)
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
