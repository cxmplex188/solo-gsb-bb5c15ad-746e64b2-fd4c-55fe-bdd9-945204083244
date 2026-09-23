"""锚点校验与分段线性时间映射。"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from .srt import format_time, parse_time


class AnchorError(ValueError):
    """锚点不合法或不满足严格递增条件。"""


@dataclass(frozen=True)
class Segment:
    x0: int
    y0: int
    slope: float


@dataclass(frozen=True)
class TimeMap:
    """由锚点构造的分段线性映射 t(原时间) -> 正确时间（毫秒）。"""

    points: list[tuple[int, int, int]]  # (原时间, 正确时间, 输入行号, 1-based)

    def map_ms(self, t: int) -> float:
        pts = self.points
        if len(pts) == 1:
            # 只有一个锚点：整体平移（斜率 1）
            return t + pts[0][1] - pts[0][0]

        if t <= pts[0][0]:
            x0, y0, _ = pts[0]
            x1, y1, _ = pts[1]
            return y0 + (t - x0) * (y1 - y0) / (x1 - x0)

        if t >= pts[-1][0]:
            x0, y0, _ = pts[-2]
            x1, y1, _ = pts[-1]
            return y1 + (t - x1) * (y1 - y0) / (x1 - x0)

        # 相邻锚点之间：以左侧锚点为基准的线性插值
        i = bisect_right([p[0] for p in pts], t) - 1
        x0, y0, _ = pts[i]
        x1, y1, _ = pts[i + 1]
        return y0 + (t - x0) * (y1 - y0) / (x1 - x0)

    @property
    def segments(self) -> list[Segment]:
        pts = self.points
        if len(pts) == 1:
            x, y, _ = pts[0]
            return [Segment(x, y, 1.0)]
        return [
            Segment(
                x0=a[0],
                y0=a[1],
                slope=(b[1] - a[1]) / (b[0] - a[0]),
            )
            for a, b in zip(pts, pts[1:])
        ]


def build_time_map(raw_anchors: list[tuple[str, str]]) -> TimeMap:
    """从 (原时间, 正确时间) 文本对构造映射。

    - 按原时间升序排序；
    - 原时间必须互不相同（严格递增）；
    - 正确时间必须严格递增；
    任一条件不满足都抛出 AnchorError 并说明是第几组锚点。
    """
    if not raw_anchors:
        raise AnchorError("至少需要 1 组锚点")

    parsed: list[tuple[int, int, int]] = []
    for pos, (raw_old, raw_new) in enumerate(raw_anchors, start=1):
        if not raw_old.strip() or not raw_new.strip():
            raise AnchorError(f"第 {pos} 组锚点的时间没有填写完整")
        try:
            old_ms = parse_time(raw_old, what=f"第 {pos} 组锚点的原时间")
        except ValueError as exc:
            raise AnchorError(str(exc)) from None
        try:
            new_ms = parse_time(raw_new, what=f"第 {pos} 组锚点的正确时间")
        except ValueError as exc:
            raise AnchorError(str(exc)) from None
        parsed.append((old_ms, new_ms, pos))

    parsed.sort(key=lambda p: p[0])

    for (x, _, pos_a), (x_next, _, pos_b) in zip(parsed, parsed[1:]):
        if x == x_next:
            raise AnchorError(
                f"原时间必须严格递增，但第 {pos_a} 组与第 {pos_b} 组锚点的原时间相同"
                f"（{format_time(x)}）"
            )

    for (_, y, pos_a), (_, y_next, pos_b) in zip(parsed, parsed[1:]):
        if y_next <= y:
            raise AnchorError(
                f"正确时间必须严格递增：按原时间排序后，第 {pos_b} 组正确时间"
                f"（{format_time(y_next)}）不晚于第 {pos_a} 组（{format_time(y)}）"
            )

    return TimeMap(points=parsed)
