from pathlib import Path
import zipfile

root = Path("app/src/main/java/com/shortsremote/app/ui/TouchpadScreen.kt")
source = root.read_text(encoding="utf-8")

source = source.replace(
    "    val isWristMotionActive by wristMotionDetector.isActive.collectAsState()\n",
    ""
)
source = source.replace(
    " * 3. Wrist movement controls cursor via motion sensors (Gyroscope / Accelerometer)\n",
    " * 3. Vertical finger swipes send mouse-wheel scroll events\n"
)
source = source.replace(
    "            .pointerInput(Unit) {\n                detectDragGestures(\n",
    "            .pointerInput(Unit) {\n                var wheelRemainder = 0f\n                detectDragGestures(\n",
    1
)
old = """                        val dx = (dragAmount.x * touchSensitivity).toInt()
                        val dy = (dragAmount.y * touchSensitivity).toInt()

                        if (dx != 0 || dy != 0) {
                            hidManager.sendMouseMove(dx, dy)
                        }"""
new = """                        // Vertical finger movement is converted to a real HID mouse-wheel report.
                        // Keep fractional movement so short swipes are not lost.
                        wheelRemainder += dragAmount.y * 0.18f
                        val wheelSteps = wheelRemainder.toInt()
                        if (wheelSteps != 0) {
                            hidManager.sendMouseWheel(wheelSteps)
                            wheelRemainder -= wheelSteps
                        }"""
if old not in source:
    raise SystemExit("Touchpad drag block did not match; refusing to build an unpatched APK.")
source = source.replace(old, new, 1)
root.write_text(source, encoding="utf-8")

# Temporary diagnostic output to safely inspect the actual Compose layout before adding mode controls.
print("TOUCHPAD_SOURCE_BEGIN")
print(source)
print("TOUCHPAD_SOURCE_END")

with zipfile.ZipFile("ShortsRemote_MouseWheel_Source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for path in Path(".").glob("**/*"):
        if path.is_file() and path.name != "ShortsRemote_MouseWheel_Source.zip" and not any(part in {".git", "build", ".gradle"} for part in path.parts):
            archive.write(path, path.as_posix())
print("Mouse-wheel patch applied.")
