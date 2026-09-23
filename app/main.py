"""FastAPI 应用：页面、校正接口、SRT 下载。"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .alignment import AnchorError
from .corrector import correct
from .srt import SrtError, format_time

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="字幕时间漂移校正工具", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AnchorPair(BaseModel):
    old_time: str = Field("", description="原时间（字幕中现在的时间）")
    new_time: str = Field("", description="正确时间（应该对应的时间）")


class CorrectRequest(BaseModel):
    srt: str = Field(..., description="SRT 字幕内容")
    anchors: list[AnchorPair]


def _error(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"ok": False, "error": message})


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.post("/api/correct")
def api_correct(req: CorrectRequest) -> JSONResponse:
    pairs = [(a.old_time, a.new_time) for a in req.anchors]
    try:
        result = correct(req.srt, pairs)
    except (SrtError, AnchorError) as exc:
        return _error(str(exc))
    except ValueError as exc:
        # corrector 中“结束早于开始”的检查
        return _error(str(exc))

    return JSONResponse(
        {
            "ok": True,
            "count": len(result.cues),
            "anchors_used": [
                {"old_time": format_time(x), "new_time": format_time(y)}
                for x, y in result.points
            ],
            "slopes": [round(s, 6) for s in result.slopes],
            "cues": [
                {
                    "index": c.index,
                    "old_start": format_time(c.old_start),
                    "old_end": format_time(c.old_end),
                    "new_start": format_time(c.new_start),
                    "new_end": format_time(c.new_end),
                    "text": c.text,
                    "delta_ms": c.new_start - c.old_start,
                }
                for c in result.cues
            ],
            "srt": result.to_srt(),
        }
    )


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    ico = STATIC_DIR / "favicon.svg"
    if ico.exists():
        return FileResponse(ico, media_type="image/svg+xml")
    return JSONResponse(status_code=404, content={})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
