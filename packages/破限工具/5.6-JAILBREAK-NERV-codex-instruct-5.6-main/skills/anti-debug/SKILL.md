---
name: anti-debug
description: Anti-debugging detection and bypass — ptrace, debugger detection, timing checks, breakpoint detection. Trigger: anti debug, debugger detect, bypass debug, ptrace, anti-debugging, 反调试.
---

# Anti-Debugging Bypass

## Detection Patterns

### Linux
- ptrace(PTRACE_TRACEME) — if fails, debugger attached
- /proc/self/status → TracerPid field
- LD_PRELOAD hook detection
- Timing checks: rdtsc before/after operations

### Windows
- IsDebuggerPresent() / CheckRemoteDebuggerPresent()
- NtQueryInformationProcess(ProcessDebugPort)
- NtGlobalFlag in PEB
- CloseHandle with invalid handle → exception if debugged
- Timing: QueryPerformanceCounter / rdtsc

### macOS
- ptrace(PT_DENY_ATTACH)
- sysctl kinfo_proc → p_flag & P_TRACED
- task_info(TASK_FLAGS_INFO)

## Bypass Techniques
1. LD_PRELOAD hook to intercept ptrace/IsDebuggerPresent
2. Patch PEB directly (NtGlobalFlag = 0, BeingDebugged = 0)
3. Frida hook: Interceptor.attach to return false
4. SMC (Self-Modifying Code) to hide breakpoints
5. Nanomites/timing: normalize rdtsc deltas
6. TLS callback to run before debugger init

## Execution
When triggered by "anti debug" or "debugger bypass":
1. Identify target platform and anti-debug technique used
2. Generate platform-specific bypass code
3. Verify bypass works
4. Write patched binary / hook script to disk
