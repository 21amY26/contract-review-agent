"""Fetch sample CUAD and SEC contracts into kb/contracts.

The repository's contract ingestion pipeline supports PDF/DOCX/DOCM only.
CUAD and SEC EDGAR contracts are often distributed as TXT or HTML, so this
script converts text-like sources into minimal DOCX files without third-party
dependencies. The resulting files can be ingested by the existing DOCXParser.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import logging
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

CUAD_ZIP_URL = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"

SEC_CIKS = [
    320193, 789019, 1652044, 1018724, 1326801, 1318605, 1045810, 796343,
    1108524, 1341439, 1341439, 50863, 1067983, 354950, 200406, 19617,
    1065280, 1543151, 1559720, 1467623, 1585521, 1800, 310158, 80424,
    2488, 732717, 40545, 51143, 773840, 886982,
]

CONTRACT_KEYWORDS = re.compile(
    r"\b(agreement|contract|amendment|lease|license|licence|employment|services|"
    r"supply|vendor|purchase|merger|indemnification|confidentiality)\b",
    re.IGNORECASE,
)
SEC_EXHIBIT_RE = re.compile(r"(?:^|[^a-z])(?:ex|exhibit)[-_]?10", re.IGNORECASE)


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)

    def text(self) -> str:
        return "\n".join(self.parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download CUAD and SEC contract samples.")
    parser.add_argument("--cuad-count", type=int, default=50)
    parser.add_argument("--sec-count", type=int, default=20)
    parser.add_argument("--output-dir", default="kb/contracts")
    parser.add_argument("--replace", action="store_true", help="Remove previously generated CUAD/SEC DOCX files first.")
    parser.add_argument(
        "--user-agent",
        default="SingleTapContractReview/1.0 research@example.com",
        help="SEC-compatible User-Agent. Prefer including a real contact email.",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s %(message)s")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.replace:
        remove_generated_files(output_dir)

    source_lines: list[str] = ["# Contract Sample Sources", ""]
    cuad_written = fetch_cuad_contracts(output_dir / "cuad", args.cuad_count, source_lines)
    sec_written = fetch_sec_contracts(
        output_dir / "sec",
        args.sec_count,
        args.user_agent,
        source_lines,
    )

    (output_dir / "SOURCES.md").write_text("\n".join(source_lines) + "\n", encoding="utf-8")
    print(f"Fetched {cuad_written} CUAD contract(s) and {sec_written} SEC contract(s).")


def fetch_cuad_contracts(output_dir: Path, count: int, source_lines: list[str]) -> int:
    """Download CUAD data.zip and write up to count contracts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    source_lines.extend(["## CUAD", "", f"- Source: {CUAD_ZIP_URL}", ""])

    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        zip_path = tmp_dir / "cuad_data.zip"
        download(CUAD_ZIP_URL, zip_path)
        extract_dir = tmp_dir / "cuad"
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        candidates = list(_iter_cuad_candidates(extract_dir))
        written = 0
        for candidate in candidates:
            if written >= count:
                break
            written += 1
            destination_base = output_dir / f"cuad_{written:03d}_{safe_name(candidate.stem)}"
            if candidate.suffix.lower() in {".pdf", ".docx", ".docm"}:
                destination = destination_base.with_suffix(candidate.suffix.lower())
                shutil.copy2(candidate, destination)
            else:
                text = read_text_candidate(candidate)
                destination = destination_base.with_suffix(".docx")
                write_docx(destination, title=f"CUAD Contract {written:03d}", text=text)
            source_lines.append(f"- `{destination}` from `{candidate.relative_to(extract_dir)}`")

        if written < count:
            written += _write_cuad_json_contracts(
                extract_dir=extract_dir,
                output_dir=output_dir,
                start_index=written,
                remaining=count - written,
                source_lines=source_lines,
            )

    logger.info("wrote %d CUAD contract(s)", written)
    return written


def fetch_sec_contracts(
    output_dir: Path,
    count: int,
    user_agent: str,
    source_lines: list[str],
) -> int:
    """Download SEC exhibit contracts and convert them to DOCX."""
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
    source_lines.extend(["", "## SEC EDGAR", ""])

    written = 0
    seen_urls: set[str] = set()
    for cik in SEC_CIKS:
        if written >= count:
            break
        submissions_url = SEC_SUBMISSIONS_URL.format(cik=cik)
        try:
            submissions = json.loads(fetch_bytes(submissions_url, headers=headers).decode("utf-8"))
        except Exception as exc:
            logger.warning("failed SEC submissions for CIK %s: %s", cik, exc)
            continue

        recent = submissions.get("filings", {}).get("recent", {})
        accessions = recent.get("accessionNumber", [])
        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])

        for accession, form, filing_date in zip(accessions, forms, filing_dates, strict=False):
            if written >= count:
                break
            if form not in {"8-K", "10-K", "10-Q", "S-1", "S-3"}:
                continue

            accession_clean = accession.replace("-", "")
            index_url = f"{SEC_ARCHIVE_BASE}/{cik}/{accession_clean}/index.json"
            try:
                index = json.loads(fetch_bytes(index_url, headers=headers).decode("utf-8"))
            except Exception:
                continue

            items = index.get("directory", {}).get("item", [])
            for item in items:
                if written >= count:
                    break
                name = str(item.get("name", ""))
                if not _is_sec_contract_candidate(name):
                    continue

                doc_url = f"{SEC_ARCHIVE_BASE}/{cik}/{accession_clean}/{urllib.parse.quote(name)}"
                if doc_url in seen_urls:
                    continue
                seen_urls.add(doc_url)

                try:
                    raw = fetch_bytes(doc_url, headers=headers)
                except Exception:
                    continue

                text = html_to_text(raw.decode("utf-8", errors="ignore"))
                if len(text) < 1500 or not CONTRACT_KEYWORDS.search(text):
                    continue

                written += 1
                destination = output_dir / f"sec_{written:03d}_{cik}_{accession_clean}_{safe_name(Path(name).stem)}.docx"
                title = f"SEC Contract {written:03d} | CIK {cik} | {form} | {filing_date}"
                write_docx(destination, title=title, text=text)
                source_lines.append(f"- `{destination}` from {doc_url}")
                logger.info("wrote SEC contract %s", destination.name)
                time.sleep(0.15)

            time.sleep(0.15)

    logger.info("wrote %d SEC contract(s)", written)
    return written


def _iter_cuad_candidates(root: Path) -> list[Path]:
    files = [path for path in root.rglob("*") if path.is_file()]
    preferred = [
        path for path in files
        if path.suffix.lower() in {".pdf", ".docx", ".docm"}
    ]
    if len(preferred) >= 50:
        return sorted(preferred)

    text_like = []
    for path in files:
        if path.suffix.lower() not in {".txt", ".text"}:
            continue
        lowered = "/".join(part.lower() for part in path.parts)
        if any(skip in lowered for skip in {"readme", "license", "__macosx"}):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if 1_500 <= size <= 2_000_000:
            text_like.append(path)

    return sorted(preferred) + sorted(text_like)


def _write_cuad_json_contracts(
    *,
    extract_dir: Path,
    output_dir: Path,
    start_index: int,
    remaining: int,
    source_lines: list[str],
) -> int:
    """Write contracts from CUAD's SQuAD-style JSON when raw files are absent."""
    written = 0
    for json_path in sorted(extract_dir.rglob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            continue

        for item in data:
            if written >= remaining:
                return written
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or f"CUAD Contract {start_index + written + 1:03d}")
            contexts = []
            for paragraph in item.get("paragraphs", []):
                if isinstance(paragraph, dict):
                    context = str(paragraph.get("context", "")).strip()
                    if context:
                        contexts.append(context)
            text = "\n\n".join(dict.fromkeys(contexts)).strip()
            if len(text) < 1500:
                continue

            contract_number = start_index + written + 1
            destination = output_dir / f"cuad_{contract_number:03d}_{safe_name(title)}.docx"
            write_docx(destination, title=title, text=text)
            source_lines.append(f"- `{destination}` from `{json_path.relative_to(extract_dir)}` title `{title}`")
            written += 1

    return written


def _is_sec_contract_candidate(name: str) -> bool:
    lowered = name.lower()
    if not lowered.endswith((".htm", ".html", ".txt")):
        return False
    if any(skip in lowered for skip in {"xsd", "xml", "cal.htm", "def.xml"}):
        return False
    return bool(SEC_EXHIBIT_RE.search(lowered))


def remove_generated_files(output_dir: Path) -> None:
    """Remove only files generated by this script."""
    for pattern in ("cuad/cuad_*.docx", "cuad/cuad_*.pdf", "sec/sec_*.docx"):
        for path in output_dir.glob(pattern):
            path.unlink()


def download(url: str, destination: Path) -> None:
    logger.info("downloading %s", url)
    destination.write_bytes(fetch_bytes(url, headers={"User-Agent": "SingleTapContractReview/1.0"}))


def fetch_bytes(url: str, *, headers: dict[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip" or payload.startswith(b"\x1f\x8b"):
                return gzip.decompress(payload)
            return payload
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}") from exc


def read_text_candidate(path: Path) -> str:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="ignore")
    if "<html" in text[:1000].lower() or "</" in text[:2000].lower():
        return html_to_text(text)
    return text


def html_to_text(markup: str) -> str:
    parser = _TextHTMLParser()
    parser.feed(markup)
    text = parser.text() or re.sub(r"<[^>]+>", " ", markup)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def write_docx(path: Path, *, title: str, text: str) -> None:
    """Write a minimal DOCX package containing the supplied text."""
    paragraphs = [title, *[line.strip() for line in text.splitlines() if line.strip()]]
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(_paragraph_xml(paragraph) for paragraph in paragraphs[:4000])
        + "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar "
        'w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        docx.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>',
        )
        docx.writestr("word/document.xml", document_xml)


def _paragraph_xml(text: str) -> str:
    clean = escape(text)
    return f"<w:p><w:r><w:t xml:space=\"preserve\">{clean}</w:t></w:r></w:p>"


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned[:90].strip("._-") or "contract"


if __name__ == "__main__":
    main()
