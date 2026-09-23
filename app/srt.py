"""SRT 解析与序列化（保留原始序号与文本）。"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 时间格式: HH:MM:SS,mmm 或 HH:MM:SS.mmm
_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})"
)


class SrtError(ValueError):
    """SRT 内容无法解析。"""


@dataclass
class Cue:
    index: str          # 原始序号字符串（原样保留）
    start: int          # 毫秒
    end: int            # 毫秒
    text: str           # 字幕文本（保留换行）


def parse_time(value: str, *, what: str = "时间") -> int:
    """将 HH:MM:SS,mmm / HH:MM:SS.mmm 解析为毫秒。"""
    m = _TIME_PART_RE.fullmatch(value.strip())
    if not m:
        raise SrtError(f"{what}格式无效：{value!r}，应为 HH:MM:SS,mmm")
    h, mi, se, ms = m.groups()
    return int(h) * 3_600_000 + int(mi) * 60_000 + int(se) * 1_000 + int(ms.ljust(3, "0"))


_TIME_PART_RE = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})")


def format_time(ms: int) -> str:
    """毫秒 -> SRT 时间字符串 HH:MM:SS,mmm（负值会被钳为 0）。"""
    if ms < 0:
        ms = 0
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def parse_srt(content: str) -> list[Cue]:
    """解析 SRT 文本。

    结构：每个块为 ``序号 / 时间行 / 文本行...``。
    序号允许缺失（此时自动编号）；时间行右侧的位置信息会被忽略。
    """
    content = (
        content.lstrip("\ufeff")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    blocks = re.split(r"\n[ \t]*\n", content.strip())

    cues: list[Cue] = []
    auto = 0
    for block_no, block in enumerate(blocks, start=1):
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue

        time_line_idx = next(
            (i for i, ln in enumerate(lines) if "-->" in ln), None
        )
        if time_line_idx is None:
            raise SrtError(
                f"第 {block_no} 个字幕块缺少时间行（应包含 ' --> '）："
                f"{lines[0][:40]!r}"
            )

        if time_line_idx == 0:
            auto += 1
            index = str(auto)
        else:
            index = "\n".join(lines[:time_line_idx]).strip()

        m = _TIME_RE.search(lines[time_line_idx])
        if not m:
            raise SrtError(
                f"字幕 {index} 的时间行格式无效：{lines[time_line_idx].strip()!r}"
            )
        g = m.groups()
        start = (
            int(g[0]) * 3_600_000 + int(g[1]) * 60_000
            + int(g[2]) * 1_000 + int(g[3].ljust(3, "0"))
        )
        end = (
            int(g[4]) * 3_600_000 + int(g[5]) * 60_000
            + int(g[6]) * 1_000 + int(g[7].ljust(3, "0"))
        )
        if end < start:
            raise SrtError(f"字幕 {index} 的结束时间早于开始时间")

        text = "\n".join(lines[time_line_idx + 1 :]).strip()
        if not text:
            raise SrtError(f"字幕 {index} 没有文本内容")

        cues.append(Cue(index=index, start=start, end=end, text=text))

    if not cues:
        raise SrtError("没有解析到任何字幕，请粘贴有效的 SRT 内容")
    return cues


def serialize_srt(cues) -> str:
    """把 (index, start, end, text) 序列化为 SRT。"""
    out: list[str] = []
    for cue in cues:
        out.append(
            f"{cue.index}\n"
            f"{format_time(cue.start)} --> {format_time(cue.end)}\n"
            f"{cue.text}\n"
        )
    return "\n".join(out)
