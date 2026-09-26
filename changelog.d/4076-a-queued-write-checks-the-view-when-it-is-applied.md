### Fixed: a queued Isaac `set_joint_positions` checks the tensor view when it is applied, not only when it is queued

Called from a worker thread with the main-thread pump running, `set_joint_positions`
validates the pose, puts an `_apply` closure on the pump's queue and answers
`status="success"`. Its stale-view refusal ran at that moment - when the call was
*made*. The closure runs later, on whichever `pump()` tick drains it, and a worker's
dynamic `add_object` / `remove_object` - or `load_scene`'s per-episode reload - can
invalidate PhysX's tensor view in between.

When that happened the drain performed the articulation read regardless. Against an
invalidated view that read is the one `remove_object` measured hanging for two
minutes, and otherwise it raises a bare `Exception` ("Failed to get DOF positions
from backend") - which is not in `pump` step 1's narrow handler, so it escaped onto
the main thread and ended `run_pump_forever`, taking a live UI session down. That is
the escape the #3343 notes described as closed; it was closed for every surface
except the queued one.

`_apply` now re-checks the flag itself, under `self._lock`. Every write that marks
the view stale is made under that lock, so the check and the read are one step
rather than a narrower window. A write that finds the view stale is dropped and
reported at WARNING, naming the robot and the remedy (`reset()`, then set the pose
again): the caller was already answered success, so the log is the only place the
drop can surface, and pump step 1 logs a failed action at DEBUG.

`tests/simulation/isaac/test_the_main_thread_pump_does_not_touch_a_stale_tensor_view.py`
carried the reason this shipped. Its operation-keyed sweep credited a tensor touch as
gated when *any enclosing* function consulted the flag, so `set_joint_positions`'
call-time check was counted for the nested closure - but an enclosing check runs when
a closure is built, not when it runs. The sweep now credits only a scope's own body,
and matches an actual read of the flag rather than any text containing its name, so a
comment mentioning `_physics_view_stale` no longer counts as a gate. Six of the file's
cells fail on the pre-fix tree, and removing only the lock fails the one that measures
it.
