from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SRT = (
    "1\n00:00:01,000 --> 00:00:03,000\n第一句\n\n"
    "2\n00:00:30,000 --> 00:00:33,000\n第二句\n\n"
    "3\n00:02:00,000 --> 00:02:05,000\n第三句\n"
)


def test_health_and_index():
    assert client.get("/api/health").json() == {"ok": True}
    page = client.get("/")
    assert page.status_code == 200
    assert "字幕时间漂移校正" in page.text


def test_correct_api_happy_path():
    resp = client.post("/api/correct", json={
        "srt": SRT,
        "anchors": [
            {"old_time": "00:00:30,000", "new_time": "00:00:33,000"},
            {"old_time": "00:02:00,000", "new_time": "00:02:10,000"},
        ],
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] and data["count"] == 3
    # 序号与文本保留
    assert [c["index"] for c in data["cues"]] == ["1", "2", "3"]
    assert data["cues"][0]["text"] == "第一句"
    # 锚点精确命中
    assert data["cues"][1]["new_start"] == "00:00:33,000"
    assert data["cues"][2]["new_start"] == "00:02:10,000"
    # 斜率 97/90 ≈ 1.0778；第一条在首锚点之前，按首段斜率外推
    # 33000 + (1000-30000)*97/90 = 1744.44 → 00:00:01,744
    first = data["cues"][0]
    assert first["new_start"] == "00:00:01,744"
    assert first["new_end"] == "00:00:03,900"
    # 第二条结束：33000 + 3000*97/90 = 36233.33
    # 下载内容就是结果 SRT
    assert "00:00:33,000 --> 00:00:36,233" in data["srt"]
    assert data["cues"][2]["new_end"] == "00:02:15,389"


def test_correct_api_rejects_bad_anchors():
    resp = client.post("/api/correct", json={
        "srt": SRT,
        "anchors": [
            {"old_time": "00:00:30,000", "new_time": "00:00:10,000"},
            {"old_time": "00:01:00,000", "new_time": "00:00:09,000"},
        ],
    })
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False and "正确时间必须严格递增" in body["error"]


def test_correct_api_rejects_bad_srt():
    resp = client.post("/api/correct", json={
        "srt": "not an srt",
        "anchors": [{"old_time": "00:00:01,000", "new_time": "00:00:02,000"}],
    })
    assert resp.status_code == 400
    assert "时间行" in resp.json()["error"]


def test_correct_api_rejects_duplicate_old_time():
    resp = client.post("/api/correct", json={
        "srt": SRT,
        "anchors": [
            {"old_time": "00:00:30,000", "new_time": "00:00:31,000"},
            {"old_time": "00:00:30,000", "new_time": "00:00:40,000"},
        ],
    })
    assert resp.status_code == 400
    assert "原时间必须严格递增" in resp.json()["error"]
