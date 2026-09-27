"""리플레이 dict → 브라우저로 여는 HTML 한 파일 (외부 파일·인터넷 없이 열림)."""

from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("viewer.html")
MARK = "/*__REPLAY__*/null"


def write_html(replay: dict, out: Path) -> Path:
    data = json.dumps(replay, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace(MARK, data, 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
