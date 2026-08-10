# Development Runtime Port Ownership Design

## Outcome

`start-test.bat` may take over the MacSoft runtime ports from the installed
`MacSoftAgentHost` service, but only after proving that every conflicting
listener belongs to that exact service process tree. Closing the development
Desktop stops the source runtime and leaves the ports released.

## Safety boundary

- Only the exact Windows service name `MacSoftAgentHost` is eligible.
- Its executable must be `pythonservice.exe` under a `MacSoft Agent/python`
  installation directory.
- Every conflicting required-port PID must be the service PID or one of its
  descendants.
- Mixed or unknown owners remain a hard failure with the port/PID summary.
- Service shutdown goes through Windows Service Control Manager, with a narrow
  UAC elevation only when the launcher itself is not elevated.
- Development shutdown never restarts the installed service. Its configured
  Windows startup policy is unchanged.

## Lifecycle

The launcher first removes stale current-source Electron processes, checks port
ownership, yields the installed service when safe, and starts the development
Host and Desktop. The existing `finally` path invokes
`stop-test-runtime.ps1`, which validates recorded process command lines, stops
their trees, and waits for all owned ports to disappear.

Local files under `tmp/` remain ignored generated artifacts and are neither
runtime inputs nor packaged Server content.
