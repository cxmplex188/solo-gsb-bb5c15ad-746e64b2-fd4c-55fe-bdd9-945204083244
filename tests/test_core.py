import pytest

from app.alignment import AnchorError, build_time_map
from app.srt import SrtError, format_time, parse_srt, parse_time, serialize_srt


def test_parse_and_format_time():
    assert parse_time("00:00:01,500") == 1500
    assert parse_time("01:02:03.040") == 3723040
    assert format_time(3723040) == "01:02:03,040"
    with pytest.raises(SrtError):
        parse_time("1:2:3")


def test_parse_srt_preserves_index_and_text():
    content = (
        "1\n00:00:01,000 --> 00:00:03,500\nHello\nWorld\n\n"
        "42\n00:00:05,000 --> 00:00:08,000\n第二行\n"
    )
    cues = parse_srt(content)
    assert len(cues) == 2
    assert cues[0].index == "1"
    assert cues[0].start == 1000 and cues[0].end == 3500
    assert cues[0].text == "Hello\nWorld"
    assert cues[1].index == "42"
    assert cues[1].text == "第二行"


def test_parse_srt_crlf_and_bom():
    content = "﻿1\r\n00:00:01,000 --> 00:00:03,500\r\nHi\r\n"
    cues = parse_srt(content)
    assert cues[0].text == "Hi"


def test_parse_srt_rejects_bad_block():
    with pytest.raises(SrtError):
        parse_srt("1\nnot a time line\nHello")
    with pytest.raises(SrtError):
        parse_srt("")
    with pytest.raises(SrtError):
        parse_srt("1\n00:00:03,000 --> 00:00:01,000\nreversed")


def test_serialize_roundtrip():
    content = "1\n00:00:01,000 --> 00:00:03,500\nHello\n"
    cues = parse_srt(content)
    out = serialize_srt(cues)
    assert "00:00:01,000 --> 00:00:03,500" in out
    assert parse_srt(out)[0].text == "Hello"


def test_single_anchor_is_pure_shift():
    tm = build_time_map([("00:00:10,000", "00:00:12,500")])
    assert tm.map_ms(0) == 2500
    assert tm.map_ms(60_000) == 62_500
    assert tm.segments[0].slope == 1.0


def test_two_anchors_linear_and_extrapolation():
    # 原 10s -> 12s；原 70s -> 75s，区间内斜率 1.05，截距 1500
    tm = build_time_map([("00:00:10,000", "00:00:12,000"),
                         ("00:01:10,000", "00:01:15,000")])
    assert tm.map_ms(10_000) == 12_000
    assert tm.map_ms(70_000) == 75_000
    # 区间内
    assert tm.map_ms(30_000) == 33_000
    # 锚点之外沿用最近区段斜率
    assert tm.map_ms(0) == 1_500
    assert tm.map_ms(130_000) == 138_000


def test_piecewise_segments_use_local_slopes():
    tm = build_time_map([
        ("00:00:00,000", "00:00:00,000"),
        ("00:00:10,000", "00:00:20,000"),   # 斜率 2
        ("00:00:30,000", "00:00:30,000"),   # 斜率 0.5
    ])
    assert tm.map_ms(5_000) == 10_000
    assert tm.map_ms(20_000) == 25_000
    # 末端外推沿用最后一段斜率 0.5
    assert tm.map_ms(40_000) == 35_000


def test_duplicate_old_time_rejected():
    with pytest.raises(AnchorError, match="原时间必须严格递增"):
        build_time_map([("00:00:10,000", "00:00:11,000"),
                        ("00:00:10,000", "00:00:12,000")])


def test_non_increasing_new_time_rejected():
    # 输入顺序不重要：按原时间排序后正确时间不严格递增
    with pytest.raises(AnchorError, match="正确时间必须严格递增"):
        build_time_map([("00:00:05,000", "00:00:20,000"),
                        ("00:00:10,000", "00:00:10,000")])


def test_equal_new_time_rejected():
    with pytest.raises(AnchorError, match="正确时间必须严格递增"):
        build_time_map([("00:00:05,000", "00:00:10,000"),
                        ("00:00:10,000", "00:00:10,000")])


def test_bad_time_format_message():
    with pytest.raises(AnchorError, match="第 2 组"):
        build_time_map([("00:00:01,000", "00:00:02,000"),
                        ("bad", "00:00:03,000")])


def test_empty_anchor_rejected():
    with pytest.raises(AnchorError):
        build_time_map([])
    with pytest.raises(AnchorError, match="没有填写完整"):
        build_time_map([("00:00:01,000", "")])
