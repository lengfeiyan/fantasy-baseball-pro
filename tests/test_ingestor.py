"""数据导入测试。"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from fantasy_baseball.core.ingestor import DataIngestor, _normalize_columns
from fantasy_baseball.db import PlayerRepository


def test_normalize_columns_maps_k_per_9():
    df = pd.DataFrame({"Name": ["X"], "K/9": [10.0], "BB/9": [3.0]})
    out = _normalize_columns(df)
    assert "name" in out.columns
    assert "K_per_9" in out.columns
    assert "BB_per_9" in out.columns


def test_normalize_columns_case_insensitive():
    df = pd.DataFrame({"NAME": ["X"], "hr": [20]})
    out = _normalize_columns(df)
    assert "name" in out.columns
    assert "HR" in out.columns


def test_ingestor_positions(fresh_conn, tmpdir, monkeypatch):
    # 准备位置 CSV
    pos_file = tmpdir.join("pos.csv")
    pos_file.write_text("Name,POS\nAlice,OF\nBob,SS\n", encoding="utf-8")

    ing = DataIngestor(conn=fresh_conn)
    monkeypatch.setattr(
        "fantasy_baseball.core.ingestor.resolve_path", lambda p: str(pos_file)
    )
    monkeypatch.setattr(ing, "config", {"data": {"positions_file": str(pos_file)}})

    n = ing.ingest_positions()
    assert n == 2
    df = PlayerRepository(fresh_conn).get_positions()
    assert len(df) == 2


def test_ingestor_single_source(fresh_conn, tmpdir, monkeypatch):
    """单源模式：从 CSV 导入打者并拷贝到 merged 表。"""
    # 准备打者 CSV（FanGraphs 风格列名）
    hitter_file = tmpdir.join("hitters.csv")
    hitter_file.write_text(
        "Name,Team,POS,R,HR,RBI,SB,AVG,OBP,SLG,OPS,PA\n"
        "TestA,TM,OF,90,25,80,15,0.290,0.370,0.520,0.890,640\n"
        "TestB,TM,1B,70,30,95,1,0.270,0.340,0.490,0.830,600\n",
        encoding="utf-8",
    )

    ing = DataIngestor(conn=fresh_conn)
    # 配置为单源模式（显式 season=2026，保持路径断言确定性，不受当前年影响）
    monkeypatch.setattr(ing, "config", {
        "data": {"season": 2026,
                 "use_multi_source": False,
                 "file_patterns": {"hitters": "x.csv", "pitchers": "y.csv"},
                 "positions_file": "none.csv"},
        "projections": {"sources": ["SINGLE"], "weights": {"STEAMER": 1.0}},
    })
    monkeypatch.setattr(
        "fantasy_baseball.core.ingestor.resolve_path",
        lambda p: str(hitter_file) if p == "data/hitters_2026.csv" else str(tmpdir / p),
    )

    n = ing.ingest_hitters()
    assert n == 2
    n_merged = ing.merge_data()["hitters_merged"]
    assert n_merged == 2


def test_ingestor_multi_source_merge(fresh_conn, tmpdir, monkeypatch):
    """多源模式：两个源按权重融合。"""
    # 两个源的打者 CSV
    s1 = tmpdir.join("hitters_2026_steamer.csv")
    s1.write_text(
        "Name,Team,POS,R,HR,RBI,SB,AVG,OBP,SLG,OPS,PA\nPlayer,TM,OF,100,20,80,10,0.280,0.350,0.500,0.850,600\n",
        encoding="utf-8",
    )
    s2 = tmpdir.join("hitters_2026_zips.csv")
    s2.write_text(
        "Name,Team,POS,R,HR,RBI,SB,AVG,OBP,SLG,OPS,PA\nPlayer,TM,OF,120,30,90,15,0.300,0.370,0.550,0.920,650\n",
        encoding="utf-8",
    )

    ing = DataIngestor(conn=fresh_conn)
    monkeypatch.setattr(ing, "config", {
        "data": {"use_multi_source": True,
                 "file_patterns": {"hitters": "hitters_2026_{source}.csv", "pitchers": "p.csv"},
                 "positions_file": "none.csv"},
        "projections": {"sources": ["STEAMER", "ZIPS"], "weights": {"STEAMER": 0.5, "ZIPS": 0.5}},
    })
    monkeypatch.setattr(
        "fantasy_baseball.core.ingestor.resolve_path",
        lambda p: str(tmpdir / os.path.basename(p)),
    )

    ing.ingest_hitters()
    ing.merge_data()
    df = PlayerRepository(fresh_conn).get_merged_hitters()
    assert len(df) == 1
    # HR 应为 (20+30)/2 = 25
    assert df.iloc[0]["HR"] == pytest.approx(25.0)
