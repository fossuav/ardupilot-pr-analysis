### Summary

A Lua script finds every binding method by name on every call: `ahrs:get_roll_rad()` goes through the type's `__index` C function, which compares the name against the type's method list one `strcmp` at a time (ahrs and vehicle have about 40 methods each). This caches each method the first time a type is indexed by that name, so later calls are a Lua table hit. A binding-heavy 50 Hz script uses 17% less CPU.

### Classification & Testing (check all that apply and add your own)

- [ ] Checked by a human programmer
- [x] Automated test(s) verify changes (e.g. unit test, autotest)
- [x] Tested manually, description below (e.g. SITL)
- [x] Tested on hardware

Measured on an RP2350 (RPI_UAVFC, #32995's branch, thread statistics build) running a 50 Hz Lua flight-mode script that makes about 45 binding calls a run; the firmware was the only difference (an earlier revision of this change, which differs only on a name's first lookup):

| | master | this PR |
|---|---|---|
| Scripting thread, share of its core | 10.3% | 8.5% |
| Script run, best / mean | 1.49 / 2.55 ms | 1.13 / 1.84 ms |
| `vehicle:get_mode()` | 14.8 us | 5.3 us |
| `ahrs:get_roll_rad()` | 14.4 us | 5.2 us |
| `vehicle:set_target_angle_and_climbrate()` | 26.0 us | 10.6 us |
| `baro:get_altitude()` (6 methods) | 6.0 us | 3.5 us |
| Lua heap in use | 27,364 B | 28,965 B |

Per-call times are the best of nine batches of 40 calls. PC sampling puts the name search (`load_function` and `strcmp`) at 1.20% of the core before and 0.08% after; the VM's own share also drops by 0.5 points, as a cached lookup no longer calls into C. Caching methods in locals by hand gains only about 0.4 points more on top.

SITL: the Rover Scripting internal test (with the new check), ScriptingLocationBindings, ScriptingSteeringAndThrottle, and Copter ScriptingFlipMode, ScriptingFlyVelocity and ScriptingAHRSSource pass. Flash: +436 bytes on MatekH743 copter.

### Description

Detail for reviewers; not needed to review the change in outline.

- The cache is filled lazily, per type, so memory goes only to methods scripts use: about 20 bytes a method plus about 50 bytes a type indexed, 1.6 KB for the script above (about 30 methods over 16 types). Filling every type's table up front would cost several KB on every board whether or not a script uses it.
- `__index` is a table rather than a C function with a cache behind it, so a hit is resolved inside the VM; that is where the 0.5 points of VM time come from. Sorting the method lists for a binary search would cost no RAM but keeps a C call and several `strcmp`s per lookup. `mt.__index = mt` would cost no extra table but lets a script read metamethods such as `__gc`.
- A miss calls the type's existing index function and keeps the answer if it is not nil, so a cache holds at most its type's methods and enums. Index functions return a C function or an enum constant and depend on the name alone, never the object (the code comment says so), which is what makes one cache right for every object of a type.
- The first lookup of a name can now allocate, so it can fail when the scripting heap is full. The cache is the metatable's last setup step, after `__index` and the operators, so a failure there leaves the type complete and uncached. A bad key (`v[true]`) still fails with an error naming `__index`.
- Scripts cannot reach a cache table: the sandbox has no `getmetatable`, `rawget` or `rawset`.

The new test passes on master as well. It checks, once and on names nothing else in the file looks up, that the first lookup of a name agrees with later ones for userdata, a singleton and an ap_object, that types with a method of the same name keep their own, that enum values hold, and that unknown names and numeric keys read nil. A cache that stored unknown names fails it.