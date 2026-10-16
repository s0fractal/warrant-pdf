"""A deterministic PDF writer: the same lines and bundle give the same bytes.

The page shows the canonical text; the bundle is an embedded file
(`warrant-bundle.json`) whose stream sits right after the marker line.
Text outside printable ASCII is shown as `?` (ADR-0005): the page is a
rendering, the verifier prints the exact UTF-8 text."""
from .bundle import embed_object

LINES_PER_PAGE = 60
WIDTH = 92


def _pdf_text(s):
    s = "".join(c if 32 <= ord(c) < 127 else "?" for c in s)
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(lines):
    out = []
    for line in lines:
        while len(line) > WIDTH:
            out.append(line[:WIDTH])
            line = "    " + line[WIDTH:]
        out.append(line)
    return out


def render(lines, bundle_bytes):
    lines = _wrap(lines)
    pages = [lines[i:i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)] or [[]]
    # Object numbers: 1 catalog, 2 pages, 3 font, 4 names, 5 filespec, 6 bundle, then page/content pairs.
    objs = {}
    page_ids = [7 + 2 * i for i in range(len(pages))]
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R /Names << /EmbeddedFiles 4 0 R >> >>"
    objs[2] = b"<< /Type /Pages /Count %d /Kids [%s] >>" % (
        len(pages), b" ".join(b"%d 0 R" % p for p in page_ids))
    objs[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"
    objs[4] = b"<< /Names [(warrant-bundle.json) 5 0 R] >>"
    objs[5] = (b"<< /Type /Filespec /F (warrant-bundle.json) /UF (warrant-bundle.json) "
               b"/EF << /F 6 0 R >> >>")
    objs[6] = b"<< /Type /EmbeddedFile /Subtype /application#2Fjson /Length %d >>\n" % len(bundle_bytes) \
        + embed_object(bundle_bytes)
    for pid, page in zip(page_ids, pages):
        ops = [b"BT /F1 9 Tf 11 TL 40 800 Td"]
        ops += [b"(" + _pdf_text(line).encode("ascii") + b") '" for line in page]
        ops.append(b"ET")
        content = b"\n".join(ops)
        objs[pid] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                     b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (pid + 1))
        objs[pid + 1] = b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    xref = len(out)
    size = max(objs) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    out += b"".join(b"%010d 00000 n \n" % offsets[n] for n in range(1, size))
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return bytes(out)
