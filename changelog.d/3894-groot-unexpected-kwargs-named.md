### Fixed: `Gr00tPolicy` names the constructor kwargs it does not read

`Gr00tPolicy(denoising_steps=8)` or `Gr00tPolicy(strict_key=True)` used to build
a policy on the defaults and say nothing: the constructor had a `**kwargs` sink
that nothing read, so a removed or misspelt option vanished with no log line
while the client dialled on as if you had passed nothing. The constructor now
warns with the sorted list of keys it ignored, the same line `LerobotLocalPolicy`
and `LerobotAsyncPolicy` already emit, so a typo shows up in the log the first
time the policy is built instead of as a default you never asked for.
