import re
from dataclasses import dataclass
from typing import Optional
import pathlib
import logging

__all__ = ["FilenameInfo", "parse_filename"]

SUPPORTED_EXTS = {"pdf", "docx", "doc", "xlsx", "xls", "txt", "png", "jpeg", "jpg", "tiff"}
DOC_TYPES = [
    "договор", "агентский_договор", "агентский-договор", "поручение", "акт"
]
DOC_TYPES_RGX = "|".join([dt.replace("_", "[_-]") for dt in DOC_TYPES])

# Гибкая регулярка: principal[_agent]_doctype_number_date.ext
FILE_RE = re.compile(
    rf"^([\w\- ]+?)(?:_([\w\- ]+?))?_({DOC_TYPES_RGX})_(\d+)_((?:\d{{6}}|\d{{8}}))(?:\.(\w+))?$",
    re.IGNORECASE
)

@dataclass
class FilenameInfo:
    principal: str
    agent: Optional[str]
    doctype: str
    number: str
    date: str
    ext: str

    @property
    def gdrive_path(self) -> str:
        parts = [self.principal]
        if self.agent:
            parts.append(self.agent)
        parts.append(self.doctype)
        return "/".join(parts) + f"/{self.number}_{self.date}"


def parse_filename(filename: str) -> Optional[FilenameInfo]:
    logger = logging.getLogger("filename_parser")
    name = pathlib.Path(filename).stem
    name = re.sub(r"\s*\(\d+\)$", "", name)
    ext = pathlib.Path(filename).suffix.lstrip('.').lower()
    logger.info(f"DEBUG: filename={filename}, name={name}, ext={ext}")
    match = FILE_RE.match(name + '.' + ext)
    if not match:
        logger.info(f"DEBUG: regex did not match for {name}.{ext}")
        return None
    principal, agent, doctype, number, date, ext_found = match.groups()
    logger.info(f"DEBUG: parsed principal={principal}, agent={agent}, doctype={doctype}, number={number}, date={date}, ext={ext_found or ext}")
    ext = ext_found or ext
    if ext not in SUPPORTED_EXTS:
        logger.info(f"DEBUG: ext {ext} not in SUPPORTED_EXTS")
        return None
    return FilenameInfo(
        principal=principal.strip(),
        agent=agent.strip() if agent else None,
        doctype=doctype.lower().replace("-", "_").replace(" ", "_"),
        number=number,
        date=date,
        ext=ext,
    ) 