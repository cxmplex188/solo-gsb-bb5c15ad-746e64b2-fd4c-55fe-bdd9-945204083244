"""把 SRT 与锚点组合起来，执行校正。"""
from __future__ import annotations

from dataclasses import dataclass

from .alignment import build_time_map
from .srt import Cue, format_time, parse_srt, serialize_srt


@dataclass
class CorrectedCue:
    index: str
    old_start: int
    old_end: int
    new_start: int
    new_end: int
    text: str


@dataclass
class CorrectionResult:
    cues: list[CorrectedCue]
    points: list[tuple[int, int]]
    slopes: list[float]

    def to_srt(self) -> str:
        mapped = [
            Cue(index=c.index, start=c.new_start, end=c.new_end, text=c.text)
            for c in self.cues
        ]
        return serialize_srt(mapped)


def _round_ms(value: float) -> int:
    return int(round(value))


def correct(srt_content: str, raw_anchors: list[tuple[str, str]]) -> CorrectionResult:
    """解析 SRT、构造映射并逐条校正。

    若校正后某条字幕的结束时间早于开始时间（极端斜率导致），
    会给出明确错误。
    """
    cues = parse_srt(srt_content)
    time_map = build_time_map(raw_anchors)

    corrected: list[CorrectedCue] = []
    for cue in cues:
        mapped_start = _round_ms(time_map.map_ms(cue.start))
        mapped_end = _round_ms(time_map.map_ms(cue.end))
        if mapped_end < 0:
            raise ValueError(
                f"字幕 {cue.index} 校正后时间早于 00:00:00,000"
                f"（结束时间映射为 {mapped_end} 毫秒），"
                "请增加更早的锚点或检查最外侧锚点的斜率"
            )
        new_start = max(0, mapped_start)
        new_end = max(0, mapped_end)
        if new_end < new_start:
            raise ValueError(
                f"字幕 {cue.index} 校正后结束时间（{format_time(new_end)}）"
                f"早于开始时间（{format_time(new_start)}），"
                "请检查锚点之间的时间跨度是否过小"
            )
        corrected.append(
            CorrectedCue(
                index=cue.index,
                old_start=cue.start,
                old_end=cue.end,
                new_start=new_start,
                new_end=new_end,
                text=cue.text,
            )
        )

    slopes = [seg.slope for seg in time_map.segments]
    return CorrectionResult(
        cues=corrected,
        points=[(x, y) for x, y, _ in time_map.points],
        slopes=slopes,
    )
