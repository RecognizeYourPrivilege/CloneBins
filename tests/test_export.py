from __future__ import annotations

from pathlib import Path

from clonebins_core.export import export_plan, subject_name
from clonebins_core.types import ClusterBin, ClusterPlan, ImageRecord, Naming, Placement
from portraits import write_identity_set


def test_subject_name_zero_pad():
    assert subject_name("subject", 1, 3) == "subject_01"
    assert subject_name("My Hero!!", 2, 12) == "My_Hero_02"


def test_export_copy_and_rename(tmp_path: Path):
    src = tmp_path / "src"
    ids = write_identity_set(src)
    dest = tmp_path / "out"
    members = [ImageRecord(path=p, relative_name=p.name) for p in ids["red"]]
    plan = ClusterPlan(clusters=[ClusterBin(index=1, name="subject_01", members=members)])
    written = export_plan(plan, dest, placement=Placement.COPY, naming=Naming.INDEX)
    assert len(written) == 3
    names = sorted(p.name for p in (dest / "subject_01").iterdir())
    assert names == ["00001.png", "00002.png", "00003.png"]
    # originals still exist (copy, not move)
    assert all(p.exists() for p in ids["red"])


def test_export_hardlink_when_possible(tmp_path: Path):
    src = tmp_path / "src"
    ids = write_identity_set(src)
    dest = tmp_path / "out"
    members = [ImageRecord(path=p, relative_name=p.name) for p in ids["blue"]]
    plan = ClusterPlan(clusters=[ClusterBin(index=1, name="subject_01", members=members)])
    export_plan(plan, dest, placement=Placement.HARDLINK, naming=Naming.KEEP)
    linked = dest / "subject_01" / "blue_01.png"
    assert linked.exists()
    # Same inode on this filesystem, or a copy fallback — either is success.
    assert linked.stat().st_size == (src / "blue_01.png").stat().st_size
