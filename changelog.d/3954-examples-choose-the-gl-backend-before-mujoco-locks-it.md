### Fixed: three examples chose their MuJoCo GL backend after it was already locked

MuJoCo reads `MUJOCO_GL` exactly once, at the first `import mujoco`, and binds
`gl_context.GLContext` there - setting the variable afterwards changes nothing. An
example that reaches that import with nothing having chosen is left on MuJoCo's own
default, `glfw`, a windowed backend that cannot create a context on a headless Linux
host. The failure is silent at the import and surfaces frames later as a render that
produces no pixels.

`examples/vla/cosmos3_diffusers_mujoco_rollout.py` regressed into this in #3866,
which moved `import mujoco` to the top of `main()` so a missing distribution costs a
second rather than the minutes a pipeline load takes. That intent is right, but the
new position is above the first `strands_robots` import - and
`strands_robots/__init__.py` runs `_mujoco_gl._configure_gl_backend()` eagerly for
precisely this reason. Before #3866 the selector had the first word and chose `egl`
on a headless host, together with the NVIDIA-ICD guarantee that prevents a silent
Mesa llvmpipe fallback; after it, neither the selector nor the file's own
`setdefault` (still sitting in the `--render` block) could take effect. Measured:
`import strands_robots.policies.cosmos3` leaves `mujoco` out of `sys.modules`, so
this was introduced rather than pre-existing.

The guarded default now sits above that import, matching the sibling
`examples/vla/cosmos3_sim_rollout.py`. Reordering the imports instead also works but
ruff rejects it (`I001`: isort wants third-party ahead of first-party in one
contiguous block, and an intervening comment does not split it).

Two more examples had the same defect and are fixed with it:
`examples/microduck/render_video.py` and `examples/wbc/wbc_g1_torque_deploy.py` each
import `mujoco` inside a helper with no default anywhere and their first
`strands_robots` import far below, so both were on `glfw` headlessly. Each now sets
the guarded default at module scope, which runs before any function body.

`tests/test_examples_mujoco_gl.py` gains a fourth rule. Its three existing rules all
grade a default's *value* - an unguarded `cgl` on any line, a module-scope default
naming one platform's backend, an offscreen backend in any scope - and none grades
its *position*, which is why this shipped. Worse, that module's docstring asserted
the premise #3866 falsified: an example "puts the default at module scope *and* at
the top of `main()`, before the lazy simulation import, and both run before mujoco is
imported."

The new rule keys on the locking event rather than on line order alone: a file that
imports `mujoco` must have either its own default or a `strands_robots` import before
that point. A `strands_robots` import is a *remedy* here, not a second hazard - the
first draft treated both as locking and reported `examples/isaac_gs/app.py` and
`examples/kimodo/kimodo_g1_dataset_headcam.py`, neither of which imports `mujoco` at
all and whose later `setdefault` is a harmless no-op because the selector already
ran. Those two are correct code, and the rule now says so.
