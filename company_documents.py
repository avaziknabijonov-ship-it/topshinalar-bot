"""Private company PDFs; deployment-owned files are never bundled with the app."""
import os
import stat
from pathlib import Path

ROUTES = {
    '/company/registration.pdf': 'company-registration.pdf',
    '/company/vat.pdf': 'vat-registration.pdf',
}
MAX_BYTES = 8 * 1024 * 1024


def read_document(path):
    filename = ROUTES[path]
    configured = os.environ.get('COMPANY_DOCUMENTS_DIR', '')
    if not configured or not Path(configured).is_absolute():
        raise FileNotFoundError('Private documents are disabled')
    directory = Path(configured).resolve()
    if directory.is_relative_to(Path(__file__).resolve().parent):
        raise FileNotFoundError('Documents must be outside the application tree')
    document = directory / filename
    if document.is_symlink():
        raise FileNotFoundError('Private document symlinks are disabled')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(document, flags), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise FileNotFoundError('Invalid private document')
        payload = stream.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES or not payload.startswith(b'%PDF-'):
        raise FileNotFoundError('Invalid private document')
    return payload, filename
