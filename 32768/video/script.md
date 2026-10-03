# PR #32768 explainer - narration script

One paragraph per scene. `make_audio.py` reads the `## sN` blocks; scene
lengths in `scenes.py` follow the generated audio.

## s1
You power up a copter and wait for a GPS lock. While you wait, the autopilot board warms up, and so does its barometer.

## s2
This is a real five-inch quad on the bench, motors off. Over three and a half minutes the board went from forty-two to sixty-two degrees, and the barometer decided the quad had sunk more than a metre. It never moved.

## s3
On ArduPilot today, once GPS has set home, arming does not clear that. It moves home to where the estimate thinks the vehicle is. Your screen reads zero, but home is filed a metre off in height above sea level. Terrain following, altitude fences and any comparison with GPS altitude carry that error for the whole flight.

## s4
This change re-zeroes the height every time you arm. Here it is in simulation, with nine and a half metres of drift injected. The height, and a false descent rate the filter had read from the drift, both drop to zero in a single sample. After that the vertical speed stays under fifteen millimetres per second, so the controller has no jump to chase.

## s5
Re-zeroing on every arm raised a second problem. The old reset moved the EKF origin, the fixed point every position is measured from. Land somewhere lower and re-arm, and your height above sea level would jump by the distance you came down. So the origin now stays put, and the drift comes out of the reference height instead.

## s6
The reset is refused where it would do harm. After a mid-air disarm, until the vehicle has come to rest. While the filter sees a metre per second or more of vertical speed. And when the height is not coming from the barometer or GPS. Re-arming while falling used to zero a fifteen metre per second descent. Now the speed carries through, and altitude hold catches the fall.

## s7
It clears drift that built up on the ground. Drift during flight needs a better temperature calibration, and that is a separate fix. Pull request thirty-two seven six eight.
