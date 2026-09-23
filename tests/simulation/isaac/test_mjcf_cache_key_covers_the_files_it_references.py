"""The USD cache key covers the closure the MJCF reads, not one directory of it.

``convert_mjcf_to_usd`` caches by content, and ``_asset_digest``'s own docstring
states the reason: keying on the named file alone would "hand back a stale USD
after any change that did not touch the one file named - which is most of them".

It walked ``dirname(mjcf_path)`` to cover that, which is the right idea and the
wrong file set. An MJCF reaches outside its own directory, and the shipped
registry's nested layouts do it by design (AGENTS.md > Registry conventions):

* ``lekiwi`` resolves to ``lekiwi/lekiwi.xml``, which ``<include>``s
  ``../so_arm100/so_arm100.xml`` - the entire arm's joints and geoms.
* ``asimov_v0`` resolves to ``xmls/asimov.xml``, which declares
  ``meshdir="../assets/meshes"`` - every mesh PhysX simulates.
* ``jvrc``, ``aliengo``, ``unitree_a1`` and ``reachy_mini`` share the shape.

So an asset re-download or an upstream update that changed ``so_arm100.xml``, or
any mesh under ``../assets/``, produced the SAME key while the entry directory
stayed byte-identical - and ``convert_mjcf_to_usd`` returned the USD built from
the old description under ``status: success``, with nothing anywhere to detect
it. The wrong ``so_arm100.xml`` is a wrong joint vocabulary, which is precisely
the joint-name parity this module exists to provide.

The collision holds in the other direction too, and that half is the one a
reader is least likely to expect: two robots whose entry directories are
identical but whose siblings differ shared one cache entry, so the second one
converted would be served the first one's USD.

These pins are filesystem-level and need no Isaac Sim: the digest is a pure
function of files on disk, so the defect and the fix are both observable by
writing two trees and comparing keys. The reviewer's own recipe -
``_asset_digest`` before and after touching a sibling - is
:meth:`TestAnIncludedSiblingChangesTheKey.test_editing_the_included_file_changes_the_key`.
"""

from __future__ import annotations

import pathlib

import pytest

pytest.importorskip("strands_robots.simulation.isaac")

from strands_robots.simulation.isaac.mjcf_assets import (  # noqa: E402 - after importorskip
    _asset_digest,
    _referenced_files,
)


def _lekiwi_layout(root: pathlib.Path, *, arm_body: str = "arm") -> pathlib.Path:
    """The ``lekiwi`` shape: an entry point including a sibling directory's file."""
    (root / "lekiwi").mkdir(parents=True)
    (root / "so_arm100").mkdir(parents=True)
    (root / "so_arm100" / "so_arm100.xml").write_text(
        f'<mujoco model="arm"><worldbody><body name="{arm_body}"/></worldbody></mujoco>',
        encoding="utf-8",
    )
    entry = root / "lekiwi" / "lekiwi.xml"
    entry.write_text(
        '<mujoco model="lekiwi"><include file="../so_arm100/so_arm100.xml"/></mujoco>',
        encoding="utf-8",
    )
    return entry


def _asimov_layout(root: pathlib.Path, *, mesh_bytes: bytes = b"solid a\nendsolid a\n") -> pathlib.Path:
    """The ``asimov_v0`` shape: ``meshdir`` pointing out of the entry directory."""
    (root / "xmls").mkdir(parents=True)
    (root / "assets" / "meshes").mkdir(parents=True)
    (root / "assets" / "meshes" / "link.stl").write_bytes(mesh_bytes)
    entry = root / "xmls" / "asimov.xml"
    entry.write_text(
        '<mujoco model="asimov">'
        '<compiler meshdir="../assets/meshes"/>'
        '<asset><mesh name="link" file="link.stl"/></asset>'
        "</mujoco>",
        encoding="utf-8",
    )
    return entry


class TestAnIncludedSiblingChangesTheKey:
    """``lekiwi``: the arm's whole description lives outside the digest root."""

    def test_the_included_file_is_part_of_the_closure(self, tmp_path: pathlib.Path) -> None:
        entry = _lekiwi_layout(tmp_path)

        referenced = _referenced_files(str(entry))

        assert str(tmp_path / "so_arm100" / "so_arm100.xml") in referenced

    def test_editing_the_included_file_changes_the_key(self, tmp_path: pathlib.Path) -> None:
        """The reviewer's recipe, and the headline defect: an upstream update to
        the arm left the key identical and served the old USD."""
        entry = _lekiwi_layout(tmp_path)
        before = _asset_digest(str(entry))

        (tmp_path / "so_arm100" / "so_arm100.xml").write_text(
            '<mujoco model="arm"><worldbody><body name="renamed_joint_vocabulary"/></worldbody></mujoco>',
            encoding="utf-8",
        )
        after = _asset_digest(str(entry))

        assert before != after, "a changed <include> target left the cache key identical"

    def test_two_trees_differing_only_outside_do_not_share_a_key(self, tmp_path: pathlib.Path) -> None:
        """The converse collision: identical entry directories, different arms."""
        left = _lekiwi_layout(tmp_path / "left", arm_body="arm")
        right = _lekiwi_layout(tmp_path / "right", arm_body="a_different_arm")

        assert _asset_digest(str(left)) != _asset_digest(str(right))

    def test_a_nested_include_is_followed(self, tmp_path: pathlib.Path) -> None:
        """An include resolves against the INCLUDING file, so the chain continues
        out of a second directory."""
        entry = _lekiwi_layout(tmp_path)
        (tmp_path / "deeper").mkdir()
        (tmp_path / "deeper" / "hand.xml").write_text('<mujoco model="hand"/>', encoding="utf-8")
        (tmp_path / "so_arm100" / "so_arm100.xml").write_text(
            '<mujoco model="arm"><include file="../deeper/hand.xml"/></mujoco>',
            encoding="utf-8",
        )
        before = _asset_digest(str(entry))

        (tmp_path / "deeper" / "hand.xml").write_text('<mujoco model="hand2"/>', encoding="utf-8")

        assert before != _asset_digest(str(entry))


class TestAMeshOutsideTheEntryDirectoryChangesTheKey:
    """``asimov_v0``: ``meshdir="../assets/meshes"``, so the simulated geometry is
    outside the digest root."""

    def test_the_mesh_is_part_of_the_closure(self, tmp_path: pathlib.Path) -> None:
        entry = _asimov_layout(tmp_path)

        referenced = _referenced_files(str(entry))

        assert str(tmp_path / "assets" / "meshes" / "link.stl") in referenced

    def test_editing_the_mesh_changes_the_key(self, tmp_path: pathlib.Path) -> None:
        entry = _asimov_layout(tmp_path)
        before = _asset_digest(str(entry))

        (tmp_path / "assets" / "meshes" / "link.stl").write_bytes(b"solid different\nendsolid different\n")

        assert before != _asset_digest(str(entry))

    def test_a_meshdir_declared_in_an_included_fragment_resolves_against_the_entry(
        self, tmp_path: pathlib.Path
    ) -> None:
        """``<compiler>`` is model-global: MuJoCo resolves a relative ``meshdir``
        against the MODEL file's directory even when an included fragment in a
        subdirectory declared it, which is the rule
        :func:`~strands_robots.simulation.isaac.loaders._parse_mjcf_mesh_assets`
        applies. Resolving it against the fragment instead would hash the wrong
        path, so the mesh would be missed exactly as before the fix."""
        (tmp_path / "frag").mkdir()
        (tmp_path / "meshes").mkdir()
        (tmp_path / "meshes" / "link.stl").write_bytes(b"one")
        (tmp_path / "frag" / "body.xml").write_text(
            '<mujoco><compiler meshdir="meshes"/><asset><mesh name="l" file="link.stl"/></asset></mujoco>',
            encoding="utf-8",
        )
        entry = tmp_path / "model.xml"
        entry.write_text('<mujoco><include file="frag/body.xml"/></mujoco>', encoding="utf-8")

        referenced = _referenced_files(str(entry))

        assert str(tmp_path / "meshes" / "link.stl") in referenced


class TestTheEntryDirectoryIsStillCovered:
    """The closure is a superset of the original walk, not a replacement.

    The walk catches files no parser models - a texture referenced from inside an
    STL, a file an importer picks up by convention - so dropping it in favour of
    the closure would trade one blind spot for another.
    """

    def test_a_sibling_inside_the_directory_still_changes_the_key(self, tmp_path: pathlib.Path) -> None:
        entry = tmp_path / "scene.xml"
        entry.write_text('<mujoco model="s"/>', encoding="utf-8")
        (tmp_path / "unreferenced.stl").write_bytes(b"a")
        before = _asset_digest(str(entry))

        (tmp_path / "unreferenced.stl").write_bytes(b"b")

        assert before != _asset_digest(str(entry))

    def test_two_entry_points_in_one_directory_differ(self, tmp_path: pathlib.Path) -> None:
        """Menagerie ships ``scene.xml`` beside the bare body, and they convert to
        different USD - the property the original digest already had."""
        (tmp_path / "scene.xml").write_text('<mujoco model="scene"/>', encoding="utf-8")
        (tmp_path / "robot.xml").write_text('<mujoco model="robot"/>', encoding="utf-8")

        assert _asset_digest(str(tmp_path / "scene.xml")) != _asset_digest(str(tmp_path / "robot.xml"))

    def test_the_key_is_stable_across_repeated_reads(self, tmp_path: pathlib.Path) -> None:
        """A digest that varied per call would miss every cache hit."""
        entry = _lekiwi_layout(tmp_path)

        assert _asset_digest(str(entry)) == _asset_digest(str(entry))


class TestABrokenReferenceIsNotAFailure:
    """This computes a cache key. Refusing to produce one would fail a conversion
    the vendor importer reports on perfectly well itself."""

    def test_a_missing_include_still_yields_a_key(self, tmp_path: pathlib.Path) -> None:
        entry = tmp_path / "model.xml"
        entry.write_text('<mujoco><include file="../nowhere/absent.xml"/></mujoco>', encoding="utf-8")

        assert isinstance(_asset_digest(str(entry)), str)

    def test_a_malformed_include_still_yields_a_key(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "frag").mkdir()
        (tmp_path / "frag" / "bad.xml").write_text("<mujoco><unclosed>", encoding="utf-8")
        entry = tmp_path / "model.xml"
        entry.write_text('<mujoco><include file="frag/bad.xml"/></mujoco>', encoding="utf-8")

        assert isinstance(_asset_digest(str(entry)), str)

    def test_a_cyclic_include_terminates(self, tmp_path: pathlib.Path) -> None:
        a = tmp_path / "a.xml"
        b = tmp_path / "b.xml"
        a.write_text('<mujoco><include file="b.xml"/></mujoco>', encoding="utf-8")
        b.write_text('<mujoco><include file="a.xml"/></mujoco>', encoding="utf-8")

        assert isinstance(_asset_digest(str(a)), str)

    def test_a_missing_reference_still_distinguishes_two_trees(self, tmp_path: pathlib.Path) -> None:
        """The path enters the manifest even when the bytes cannot, so two trees
        differing only in which absent file they name do not collide."""
        left = tmp_path / "left"
        right = tmp_path / "right"
        for directory, target in ((left, "absent_one.xml"), (right, "absent_two.xml")):
            directory.mkdir()
            (directory / "model.xml").write_text(f'<mujoco><include file="../{target}"/></mujoco>', encoding="utf-8")

        assert _asset_digest(str(left / "model.xml")) != _asset_digest(str(right / "model.xml"))


def _two_directory_layout(
    root: pathlib.Path,
    *,
    mesh_bytes: bytes = b"solid real\nendsolid real\n",
    texture_bytes: bytes = b"\x89PNG-real",
) -> pathlib.Path:
    """One ``<compiler>`` carrying ``meshdir`` AND ``texturedir``.

    The ordinary Menagerie shape, and the one a single shared asset base cannot
    serve: MuJoCo resolves ``mesh`` / ``hfield`` / ``skin`` against ``meshdir`` and
    ``texture`` against ``texturedir``, so a closure that keeps one "last directory
    seen" sends one of the two kinds to the wrong place.
    """
    (root / "model").mkdir(parents=True)
    (root / "meshes").mkdir(parents=True)
    (root / "textures").mkdir(parents=True)
    (root / "meshes" / "arm.stl").write_bytes(mesh_bytes)
    (root / "textures" / "skin.png").write_bytes(texture_bytes)
    entry = root / "model" / "scene.xml"
    entry.write_text(
        '<mujoco model="probe">'
        '<compiler meshdir="../meshes" texturedir="../textures"/>'
        '<asset><mesh name="arm" file="arm.stl"/><texture name="skin" file="skin.png"/></asset>'
        "</mujoco>",
        encoding="utf-8",
    )
    return entry


class TestEachAssetKindResolvesAgainstItsOwnDeclaredDirectory:
    """``meshdir`` and ``texturedir`` in one ``<compiler>`` are two bases, not one.

    Collecting every declared directory into one list and keeping the last entry
    made ``texturedir`` win - the attribute order the collection loop happens to
    iterate - so every mesh resolved under the texture directory, missed, and
    contributed the ``<unreadable>`` constant instead of its bytes. The digest then
    did not move when the geometry PhysX simulates changed, which is the staleness
    the closure exists to prevent, served under ``status="success"`` from a cache
    that persists across processes.

    Every cell here passes with a single shared base ONLY if that base happens to
    be the mesh one, so the texture half is what keeps the fix honest rather than
    re-inverted.
    """

    def test_every_referenced_file_resolves_to_something_on_disk(self, tmp_path: pathlib.Path) -> None:
        """The direct symptom. Pre-fix the mesh resolved into ``textures/``, a path
        that does not exist, so it entered the manifest as a name and no bytes."""
        entry = _two_directory_layout(tmp_path)

        unresolved = [path for path in _referenced_files(str(entry)) if not pathlib.Path(path).is_file()]

        assert unresolved == [], f"these resolved to a path that does not exist: {unresolved}"

    def test_the_mesh_resolves_under_meshdir(self, tmp_path: pathlib.Path) -> None:
        entry = _two_directory_layout(tmp_path)

        resolved = _referenced_files(str(entry))

        assert str(tmp_path / "meshes" / "arm.stl") in resolved

    def test_the_texture_resolves_under_texturedir(self, tmp_path: pathlib.Path) -> None:
        entry = _two_directory_layout(tmp_path)

        resolved = _referenced_files(str(entry))

        assert str(tmp_path / "textures" / "skin.png") in resolved

    def test_editing_the_mesh_changes_the_key(self, tmp_path: pathlib.Path) -> None:
        """The consequence the cache is keyed on: the geometry changed, so the USD
        built from it must not be reused."""
        entry = _two_directory_layout(tmp_path)
        before = _asset_digest(str(entry))

        (tmp_path / "meshes" / "arm.stl").write_bytes(b"solid changed\nendsolid changed\n")

        assert _asset_digest(str(entry)) != before

    def test_editing_the_texture_changes_the_key(self, tmp_path: pathlib.Path) -> None:
        """The other half, which a shared mesh base would miss."""
        entry = _two_directory_layout(tmp_path)
        before = _asset_digest(str(entry))

        (tmp_path / "textures" / "skin.png").write_bytes(b"\x89PNG-changed")

        assert _asset_digest(str(entry)) != before

    def test_assetdir_is_the_fallback_for_both_kinds(self, tmp_path: pathlib.Path) -> None:
        """With no kind-specific declaration, ``assetdir`` serves both - so it must
        not be shadowed by the per-kind slots being empty."""
        (tmp_path / "model").mkdir()
        (tmp_path / "shared").mkdir()
        (tmp_path / "shared" / "arm.stl").write_bytes(b"solid a\n")
        (tmp_path / "shared" / "skin.png").write_bytes(b"PNG-a")
        entry = tmp_path / "model" / "scene.xml"
        entry.write_text(
            '<mujoco model="p"><compiler assetdir="../shared"/>'
            '<asset><mesh name="a" file="arm.stl"/><texture name="s" file="skin.png"/></asset>'
            "</mujoco>",
            encoding="utf-8",
        )

        resolved = _referenced_files(str(entry))

        assert str(tmp_path / "shared" / "arm.stl") in resolved
        assert str(tmp_path / "shared" / "skin.png") in resolved

    def test_a_kind_specific_directory_beats_assetdir(self, tmp_path: pathlib.Path) -> None:
        """MuJoCo's precedence: ``meshdir`` / ``texturedir`` override ``assetdir``
        for the kind they name, and ``assetdir`` still serves the other."""
        (tmp_path / "model").mkdir()
        for name in ("shared", "meshes"):
            (tmp_path / name).mkdir()
        (tmp_path / "meshes" / "arm.stl").write_bytes(b"solid a\n")
        (tmp_path / "shared" / "skin.png").write_bytes(b"PNG-a")
        entry = tmp_path / "model" / "scene.xml"
        entry.write_text(
            '<mujoco model="p"><compiler assetdir="../shared" meshdir="../meshes"/>'
            '<asset><mesh name="a" file="arm.stl"/><texture name="s" file="skin.png"/></asset>'
            "</mujoco>",
            encoding="utf-8",
        )

        resolved = _referenced_files(str(entry))

        assert str(tmp_path / "meshes" / "arm.stl") in resolved
        assert str(tmp_path / "shared" / "skin.png") in resolved

    def test_the_last_declaration_of_one_attribute_wins(self, tmp_path: pathlib.Path) -> None:
        """Per attribute, not across them - the distinction the flattened list
        lost. Two ``<compiler>`` elements each naming ``meshdir``: the later one
        is the model's."""
        (tmp_path / "model").mkdir()
        for name in ("first", "second"):
            (tmp_path / name).mkdir()
            (tmp_path / name / "arm.stl").write_bytes(f"solid {name}\n".encode())
        entry = tmp_path / "model" / "scene.xml"
        entry.write_text(
            '<mujoco model="p"><compiler meshdir="../first"/><compiler meshdir="../second"/>'
            '<asset><mesh name="a" file="arm.stl"/></asset>'
            "</mujoco>",
            encoding="utf-8",
        )

        resolved = _referenced_files(str(entry))

        assert str(tmp_path / "second" / "arm.stl") in resolved
        assert str(tmp_path / "first" / "arm.stl") not in resolved
