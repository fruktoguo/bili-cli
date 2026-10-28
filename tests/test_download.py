import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bili_cli.commands import video as video_cmd
from bili_cli.main import app


FAKE_PLAYURL_DASH = {
    "dash": {
        "video": [
            {"id": 80, "codecs": "avc1.640032", "bandwidth": 2500000, "baseUrl": "http://cdn/v_80_avc"},
            {"id": 80, "codecs": "hev1.1.6.L150.90", "bandwidth": 1200000, "baseUrl": "http://cdn/v_80_hevc"},
            {"id": 64, "codecs": "avc1.640028", "bandwidth": 1500000, "baseUrl": "http://cdn/v_64_avc"},
            {"id": 32, "codecs": "avc1.64001F", "bandwidth": 600000, "baseUrl": "http://cdn/v_32_avc"},
            {"id": 16, "codecs": "avc1.64001E", "bandwidth": 300000, "baseUrl": "http://cdn/v_16_avc"},
        ],
        "audio": [
            {"id": 30280, "bandwidth": 192000, "baseUrl": "http://cdn/a_192"},
            {"id": 30216, "bandwidth": 64000, "baseUrl": "http://cdn/a_64"},
        ],
    }
}

FAKE_PLAYURL_DURL = {
    "quality": 32,
    "durl": [{"url": "http://cdn/durl_video.mp4"}],
}


def test_pick_download_streams_quality():
    v, a, qn, codec = video_cmd._pick_download_streams(FAKE_PLAYURL_DASH, quality="best", codec="h264")
    assert qn == 80 and codec == "avc1.640032" and v["baseUrl"] == "http://cdn/v_80_avc"
    assert a["baseUrl"] == "http://cdn/a_192"

    v, a, qn, codec = video_cmd._pick_download_streams(FAKE_PLAYURL_DASH, quality="720p", codec="h264")
    assert qn == 64 and v["baseUrl"] == "http://cdn/v_64_avc"

    v, a, qn, codec = video_cmd._pick_download_streams(FAKE_PLAYURL_DASH, quality="360p", codec="h264")
    assert qn == 16 and v["baseUrl"] == "http://cdn/v_16_avc"


def test_pick_download_streams_codec():
    v, a, qn, codec = video_cmd._pick_download_streams(FAKE_PLAYURL_DASH, quality="1080p", codec="hevc")
    assert qn == 80 and codec == "hev1.1.6.L150.90" and v["baseUrl"] == "http://cdn/v_80_hevc"


def test_pick_download_streams_durl_fallback():
    v, a, qn, codec = video_cmd._pick_download_streams(FAKE_PLAYURL_DURL, quality="best", codec="h264")
    assert v["url"] == "http://cdn/durl_video.mp4"
    assert a is None
    assert codec == "durl"


def test_to_srt_formatting():
    items = [
        {"from": 1.25, "to": 3.75, "content": "第一句话"},
        {"from": 4.0, "to": 6.5, "content": "第二句话"},
    ]
    srt = video_cmd._to_srt(items)
    assert "1\n00:00:01,250 --> 00:00:03,750\n第一句话\n" in srt
    assert "2\n00:00:04,000 --> 00:00:06,500\n第二句话\n" in srt


class FakeDanmaku:
    def __init__(self):
        self.text = "前方高能"
        self.dm_time = 12.345
        self.send_time = 1700000000.0
        self.color = "ffffff"
        self.mode = 1
        self.font_size = 25
        self.pool = 0
        self.crc32_id = "abc123"
        self.id_ = 99999


def test_to_danmaku_xml():
    xml = video_cmd._to_danmaku_xml([FakeDanmaku()])
    assert '<?xml version="1.0" encoding="UTF-8"?>' in xml
    assert '<d p="12.345,1,25,16777215,1700000000,0,abc123,99999">前方高能</d>' in xml


class FakeVideo:
    def __init__(self, *args, **kwargs):
        pass

    async def get_info(self):
        return {
            "bvid": "BV1test",
            "title": "测试/视频?名称",
            "pages": [{"page": 1, "cid": 1001, "part": "P1", "duration": 120}],
        }

    async def get_download_url(self, cid):
        return FAKE_PLAYURL_DASH

    async def get_subtitle(self, cid):
        return {"subtitles": []}

    async def get_danmakus(self, page_index):
        return []


def test_download_dry_run_cli(monkeypatch, tmp_path):
    monkeypatch.setattr(video_cmd, "_video", lambda vid: FakeVideo())
    runner = CliRunner()
    res = runner.invoke(app, ["--dry-run", "video", "download", "BV1test", "-o", str(tmp_path)])
    assert res.exit_code == 0
    data = json.loads(res.stdout)["data"]
    assert data["dry_run"] is True
    assert data["action"] == "video.download"
    assert data["params"]["bvid"] == "BV1test"
    assert data["params"]["quality"] == "1080P 高清"
    assert data["params"]["codec"] == "avc1.640032"


def test_download_cached_file(monkeypatch, tmp_path):
    monkeypatch.setattr(video_cmd, "_video", lambda vid: FakeVideo())
    target = tmp_path / "custom.mp4"
    target.write_bytes(b"x" * 2000)

    runner = CliRunner()
    res = runner.invoke(app, ["video", "download", "BV1test", "-o", str(target)])
    assert res.exit_code == 0
    data = json.loads(res.stdout)["data"]
    assert data["cached"] is True
    assert data["path"] == str(target.resolve())
