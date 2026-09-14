### Fixed: the custom-policy walkthrough's first policy runs on the arm it is shown driving

The opening `MyPolicy` in `docs/policies/custom-policies.md` returned an action keyed `motor.0` and `motor.1`, names no arm carries, so the page's own `run_policy` on `Robot("so100")` was refused with `status=error` ("100% unresolved keys ... the robot has not moved"). The fence now builds its action from the keys the runtime passes to `set_robot_state_keys`, which is what that method is for, and the usage block completes.
