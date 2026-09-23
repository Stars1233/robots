### Fixed: the USD cache key resolves each MJCF asset kind against its own directory

`_referenced_files` collected `meshdir`, `assetdir` and `texturedir` into one list
and kept the **last** entry as a single shared base. The collection loop visits the
three attributes in that order, so a model with one
`<compiler meshdir="../meshes" texturedir="../textures"/>` - an ordinary Menagerie
shape - ended up resolving *every* asset under the texture directory. That is the
reverse of MuJoCo's rule and of the closure's own docstring, which claimed
`meshdir` took precedence.

Two compounding defects: the precedence was inverted, and one base cannot be right
for both kinds in the first place. MuJoCo resolves `mesh` / `hfield` / `skin`
against `meshdir` and `texture` against `texturedir`, with `assetdir` the fallback
for both.

The consequence was silent and outlived the process. A mesh resolved into the
texture directory does not exist, so it folded into the manifest as the
`<unreadable>` constant and its real bytes never entered the key - the digest did
not move when the geometry PhysX actually simulates changed, and a stale USD with
the old collision geometry was served under `status: success`. Measured on the
pre-fix tree: editing the mesh left the digest byte-identical.

This mattered most before shipping rather than after, because the digest is the key
of a cross-process cache under `~/.strands_robots/asset_cache/usd_robots`. Any entry
written under a wrong key would keep serving stale geometry unless the key
derivation itself invalidated it, so fixing it now costs nothing and fixing it later
costs a cache-migration story.

`meshdir` / `assetdir` / `texturedir` are now tracked as separate
last-declaration-wins values, and the base is chosen per asset kind, matching
`loaders._parse_mjcf_mesh_assets` - which already broke on first match and is the
sibling this closure's docstring cites for its rules.

`tests/simulation/isaac/test_mjcf_cache_key_covers_the_files_it_references.py` only
exercised single-directory compilers, which is why it passed throughout. It now
carries a two-directory class covering both kinds, the `assetdir` fallback, the
kind-specific override, and per-attribute last-declaration-wins. 4 of its cells fail
on the pre-fix resolution.
