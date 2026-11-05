from pathlib import Path
import zipfile

root = Path("app/src/main/java/com/shortsremote/app/ui/TouchpadScreen.kt")
source = root.read_text(encoding="utf-8")

# Remove the old wrist-motion status dependency and its unused visual icon.
source = source.replace(
    "    val isWristMotionActive by wristMotionDetector.isActive.collectAsState()\n",
    ""
)
source = source.replace(
    "import androidx.compose.material.icons.filled.Vibration\n",
    ""
)

# Add a screen-local mode switch: false = touchpad, true = mouse wheel.
anchor = "    val touchSensitivity = 1.6f\n"
if anchor not in source:
    raise SystemExit("Could not find touch sensitivity declaration.")
source = source.replace(
    anchor,
    anchor + "    var wheelMode by remember { mutableStateOf(false) }\n",
    1
)

# The drag recognizer must restart when the selected mode changes.
source = source.replace(
    "            .pointerInput(Unit) {\n                detectDragGestures(\n",
    "            .pointerInput(wheelMode) {\n                var wheelRemainder = 0f\n                detectDragGestures(\n",
    1
)

old_drag = """                        val dx = (dragAmount.x * touchSensitivity).toInt()
                        val dy = (dragAmount.y * touchSensitivity).toInt()

                        if (dx != 0 || dy != 0) {
                            hidManager.sendMouseMove(dx, dy)
                        }"""
new_drag = """                        if (wheelMode) {
                            // Finger swipe up/down becomes a mouse-wheel event.
                            wheelRemainder += -dragAmount.y * 0.18f
                            val wheelSteps = wheelRemainder.toInt()
                            if (wheelSteps != 0) {
                                hidManager.sendMouseWheel(wheelSteps)
                                wheelRemainder -= wheelSteps
                            }
                        } else {
                            val dx = (dragAmount.x * touchSensitivity).toInt()
                            val dy = (dragAmount.y * touchSensitivity).toInt()
                            if (dx != 0 || dy != 0) {
                                hidManager.sendMouseMove(dx, dy)
                            }
                        }"""
if old_drag not in source:
    # Accept an already-patched wheel-only drag block when rebuilding from a modified source archive.
    old_wheel = """                        wheelRemainder += dragAmount.y * 0.18f
                        val wheelSteps = wheelRemainder.toInt()
                        if (wheelSteps != 0) {
                            hidManager.sendMouseWheel(wheelSteps)
                            wheelRemainder -= wheelSteps
                        }"""
    if old_wheel not in source:
        raise SystemExit("Touchpad drag block did not match; refusing to build.")
    source = source.replace(old_wheel, new_drag, 1)
else:
    source = source.replace(old_drag, new_drag, 1)

# Update the title and on-screen instructions for the active mode.
source = source.replace(
    'text = "터치패드",',
    'text = if (wheelMode) "마우스 휠" else "터치패드",',
    1
)
source = source.replace(
    'tint = if (isWristMotionActive) HeartPink else AccentBlue,',
    'tint = if (wheelMode) HeartPink else AccentBlue,',
    1
)
source = source.replace(
    'text = if (isWristMotionActive) "손목 움직임 모드 동작 중" else "화면 드래그 = 마우스 이동\\n탭 = 클릭",',
    'text = if (wheelMode) "위아래로 밀기 = 웹툰 스크롤\\n탭 = 클릭" else "손가락 이동 = 마우스 이동\\n탭 = 클릭",',
    1
)
source = source.replace(
    'color = if (isWristMotionActive) HeartPink else TextMuted,',
    'color = if (wheelMode) HeartPink else TextMuted,',
    1
)

# Replace the old wrist-motion toggle with the touchpad / wheel mode toggle.
start_marker = "            // Bottom Bar: Wrist Motion Toggle Button"
end_marker = "            }\n        }\n    }\n}"
start = source.find(start_marker)
if start == -1:
    raise SystemExit("Could not find old wrist-motion button.")
end = source.find(end_marker, start)
if end == -1:
    raise SystemExit("Could not find end of old wrist-motion button.")
replacement = """            // Switch between touchpad cursor control and mouse-wheel scrolling.
            Button(
                onClick = {
                    view.performHapticFeedback(HapticFeedbackConstants.TOGGLE_ON)
                    wheelMode = !wheelMode
                },
                modifier = Modifier
                    .fillMaxWidth(0.85f)
                    .height(42.dp)
                    .padding(bottom = 6.dp),
                shape = RoundedCornerShape(21.dp),
                colors = ButtonDefaults.buttonColors(
                    backgroundColor = if (wheelMode) ShortsRedDark else DarkSurfaceElevated,
                    contentColor = TextWhite
                )
            ) {
                Text(
                    text = if (wheelMode) "터치패드로 전환" else "마우스 휠로 전환",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }
"""
source = source[:start] + replacement + source[end + len("            }\n"):]

# Verify that no wrist-mode UI references remain.
for forbidden in ("isWristMotionActive", "wristMotionDetector.toggle()", "Icons.Default.Vibration"):
    if forbidden in source:
        raise SystemExit("Old wrist-motion UI remains: " + forbidden)

print("\n--- TouchpadScreen.kt lines 205-230 ---")
for number, line in enumerate(source.splitlines(), 1):
    if 205 <= number <= 230:
        print(f"{number}: {line}")

root.write_text(source, encoding="utf-8")

with zipfile.ZipFile("ShortsRemote_MouseWheel_Source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for path in Path(".").glob("**/*"):
        if path.is_file() and path.name != "ShortsRemote_MouseWheel_Source.zip" and not any(part in {".git", "build", ".gradle"} for part in path.parts):
            archive.write(path, path.as_posix())

print("Touchpad / mouse-wheel mode switch patch applied.")
