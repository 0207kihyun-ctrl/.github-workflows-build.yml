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
    'text = "마우스 휠",',
    1
)
source = source.replace(
    'tint = if (isWristMotionActive) HeartPink else AccentBlue,',
    'tint = if (wheelMode) HeartPink else AccentBlue,',
    1
)
source = source.replace(
    'text = if (isWristMotionActive) "손목 움직임 모드 동작 중" else "화면 드래그 = 마우스 이동\\n탭 = 클릭",',
    'text = "손가락을 위아래로 밀기 = 스크롤\\n탭 = 클릭",',
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
replacement = ""
source = source[:start] + "        }\n    }\n}" + source[end + len(end_marker):]

# Normalize any remaining status references after the wrist-mode UI removal.
source = source.replace("isWristMotionActive", "wheelMode")

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


# Use ONE serialized sender for cursor, wheel, and click reports.
# Separate mouse send loops can overlap BluetoothHidDevice.sendReport calls.
manager = Path("app/src/main/java/com/shortsremote/app/bluetooth/BluetoothHidManager.kt")
ms = manager.read_text(encoding="utf-8")
old_move = """    @SuppressLint("MissingPermission")
    fun sendMouseMove(dx: Int, dy: Int, buttons: Byte = HidPayloads.MOUSE_BUTTON_NONE) {
        val proxy = hidDevice ?: return
        val target = connectedDevice ?: return

        val report = HidPayloads.mouseReport(buttons = buttons, dx = dx, dy = dy, wheel = 0)
        proxy.sendReport(target, HidReportDescriptor.REPORT_ID_MOUSE.toInt(), report)
    }"""
old_wheel = """    @SuppressLint("MissingPermission")
    fun sendMouseWheel(wheelDelta: Int) {
        val proxy = hidDevice ?: return
        val target = connectedDevice ?: return

        val report = HidPayloads.mouseReport(buttons = HidPayloads.MOUSE_BUTTON_NONE, dx = 0, dy = 0, wheel = wheelDelta)
        proxy.sendReport(target, HidReportDescriptor.REPORT_ID_MOUSE.toInt(), report)
    }"""
old_click = """    @SuppressLint("MissingPermission")
    fun sendMouseClick() {
        val proxy = hidDevice ?: return
        val target = connectedDevice ?: return

        scope.launch {
            val downReport = HidPayloads.mouseReport(buttons = HidPayloads.MOUSE_BUTTON_LEFT, dx = 0, dy = 0)
            proxy.sendReport(target, HidReportDescriptor.REPORT_ID_MOUSE.toInt(), downReport)

            delay(35)

            val upReport = HidPayloads.mouseReport(buttons = HidPayloads.MOUSE_BUTTON_NONE, dx = 0, dy = 0)
            proxy.sendReport(target, HidReportDescriptor.REPORT_ID_MOUSE.toInt(), upReport)
            _lastLog.value = "마우스 클릭 전송 (Left Click)"
        }
    }"""
new_block = """    private val mouseReportLock = Any()
    private var pendingMouseDx = 0
    private var pendingMouseDy = 0
    private var pendingMouseWheel = 0
    private var pendingMouseClicks = 0
    private var mouseReportFlushRunning = false

    private fun enqueueMouseInput(dx: Int = 0, dy: Int = 0, wheel: Int = 0, click: Boolean = false) {
        val start = synchronized(mouseReportLock) {
            pendingMouseDx = (pendingMouseDx + dx).coerceIn(-2048, 2048)
            pendingMouseDy = (pendingMouseDy + dy).coerceIn(-2048, 2048)
            pendingMouseWheel = (pendingMouseWheel + wheel).coerceIn(-1024, 1024)
            if (click) pendingMouseClicks = (pendingMouseClicks + 1).coerceAtMost(8)
            if (mouseReportFlushRunning) false else {
                mouseReportFlushRunning = true
                true
            }
        }
        if (!start) return

        scope.launch {
            while (true) {
                val batch = synchronized(mouseReportLock) {
                    if (pendingMouseClicks == 0 && pendingMouseDx == 0 &&
                        pendingMouseDy == 0 && pendingMouseWheel == 0) {
                        mouseReportFlushRunning = false
                        null
                    } else if (pendingMouseClicks > 0) {
                        pendingMouseClicks--
                        Triple(0, 0, Int.MIN_VALUE)
                    } else {
                        val x = pendingMouseDx.coerceIn(-127, 127)
                        val y = pendingMouseDy.coerceIn(-127, 127)
                        val w = pendingMouseWheel.coerceIn(-127, 127)
                        pendingMouseDx -= x
                        pendingMouseDy -= y
                        pendingMouseWheel -= w
                        Triple(x, y, w)
                    }
                } ?: return@launch

                val proxy = hidDevice
                val target = connectedDevice
                if (proxy != null && target != null) {
                    try {
                        if (batch.third == Int.MIN_VALUE && batch.first == 0 && batch.second == 0) {
                            val down = HidPayloads.mouseReport(
                                buttons = HidPayloads.MOUSE_BUTTON_LEFT, dx = 0, dy = 0, wheel = 0
                            )
                            proxy.sendReport(target, HidReportDescriptor.REPORT_ID_MOUSE.toInt(), down)
                            delay(35)
                            val up = HidPayloads.mouseReport(
                                buttons = HidPayloads.MOUSE_BUTTON_NONE, dx = 0, dy = 0, wheel = 0
                            )
                            proxy.sendReport(target, HidReportDescriptor.REPORT_ID_MOUSE.toInt(), up)
                        } else {
                            val report = HidPayloads.mouseReport(
                                buttons = HidPayloads.MOUSE_BUTTON_NONE,
                                dx = batch.first, dy = batch.second, wheel = batch.third
                            )
                            if (!proxy.sendReport(target, HidReportDescriptor.REPORT_ID_MOUSE.toInt(), report)) {
                                Log.w(TAG, "Serialized mouse report rejected")
                            }
                        }
                    } catch (e: Exception) {
                        Log.e(TAG, "Serialized mouse report failed", e)
                    }
                }
                delay(20)
            }
        }
    }

    @SuppressLint("MissingPermission")
    fun sendMouseMove(dx: Int, dy: Int, buttons: Byte = HidPayloads.MOUSE_BUTTON_NONE) {
        if (dx != 0 || dy != 0) enqueueMouseInput(dx = dx, dy = dy)
    }

    @SuppressLint("MissingPermission")
    fun sendMouseWheel(wheelDelta: Int) {
        if (wheelDelta != 0) enqueueMouseInput(wheel = wheelDelta)
    }

    @SuppressLint("MissingPermission")
    fun sendMouseClick() {
        enqueueMouseInput(click = true)
        _lastLog.value = "마우스 클릭 대기열 등록"
    }"""


if old_move not in ms or old_wheel not in ms or old_click not in ms:
    raise SystemExit("Mouse HID functions did not match; refusing unsafe patch.")
ms = ms.replace(old_move, new_block, 1)
ms = ms.replace(old_wheel, "", 1)
ms = ms.replace(old_click, "", 1)
manager.write_text(ms, encoding="utf-8")
print("Unified serialized mouse HID queue patch applied.")


# Add a dedicated Shorts / Webtoon mode to the main remote buttons.
main_file = Path("app/src/main/java/com/shortsremote/app/ui/MainShortsScreen.kt")
main_source = main_file.read_text(encoding="utf-8")

state_anchor = "    var heartActiveCount by remember { mutableStateOf(0) }"
if "var webtoonMode by remember" not in main_source:
    if state_anchor not in main_source:
        raise SystemExit("Main screen state anchor not found; refusing to patch.")
    main_source = main_source.replace(
        state_anchor,
        state_anchor + "\n    var webtoonMode by remember { mutableStateOf(false) }",
        1
    )

next_action = "                        hidManager.sendNextShort()"
prev_action = "                        hidManager.sendPrevShort()"
if next_action not in main_source or prev_action not in main_source:
    raise SystemExit("Shorts button actions not found; refusing to patch.")

main_source = main_source.replace(
    next_action,
    "                        if (webtoonMode) hidManager.sendMouseWheel(2) else hidManager.sendNextShort()",
    1
)
main_source = main_source.replace(
    prev_action,
    "                        if (webtoonMode) hidManager.sendMouseWheel(-2) else hidManager.sendPrevShort()",
    1
)

main_source = main_source.replace(
    'text = "다음 쇼츠",',
    'text = if (webtoonMode) "위로 스크롤" else "다음 쇼츠",',
    1
)
main_source = main_source.replace(
    'contentDescription = "다음 쇼츠",',
    'contentDescription = if (webtoonMode) "위로 스크롤" else "다음 쇼츠",',
    1
)
main_source = main_source.replace(
    'text = "이전 쇼츠",',
    'text = if (webtoonMode) "아래로 스크롤" else "이전 쇼츠",',
    1
)
main_source = main_source.replace(
    'contentDescription = "이전 쇼츠",',
    'contentDescription = if (webtoonMode) "아래로 스크롤" else "이전 쇼츠",',
    1
)

footer_old = """                Text(
                    text = "터치패드 이동 →",
                    fontSize = 11.sp,
                    color = AccentBlue,
                    modifier = Modifier.clickable { onNavigateToTouchpad() }
                )"""
footer_new = """                Text(
                    text = if (webtoonMode) "웹툰 모드 · 눌러서 쇼츠 모드" else "쇼츠 모드 · 눌러서 웹툰 모드",
                    fontSize = 11.sp,
                    color = AccentBlue,
                    modifier = Modifier.clickable { webtoonMode = !webtoonMode }
                )"""
if footer_old not in main_source:
    raise SystemExit("Main screen footer anchor not found; refusing to patch.")
main_source = main_source.replace(footer_old, footer_new, 1)

main_file.write_text(main_source, encoding="utf-8")
print("Shorts/Webtoon ▲▼ mode patch applied.")


# WearMouse-style picker for already paired Bluetooth hosts.
from pathlib import Path
manager = Path("app/src/main/java/com/shortsremote/app/bluetooth/BluetoothHidManager.kt")
ms = manager.read_text(encoding="utf-8")
anchor = "    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()"
if "val pairedDevices: StateFlow<List<BluetoothDevice>>" not in ms:
    if anchor not in ms: raise SystemExit("HID state anchor missing")
    ms = ms.replace(anchor, anchor + """

    private val _pairedDevices = MutableStateFlow<List<BluetoothDevice>>(emptyList())
    val pairedDevices: StateFlow<List<BluetoothDevice>> = _pairedDevices.asStateFlow()
""", 1)

anchor = "    @SuppressLint(\"MissingPermission\")\n    private fun registerHidApp() {"
if "fun refreshPairedDevices()" not in ms:
    if anchor not in ms: raise SystemExit("HID register anchor missing")
    methods = """    @SuppressLint("MissingPermission")
    fun refreshPairedDevices() {
        val adapter = bluetoothAdapter
        if (adapter == null || !adapter.isEnabled) {
            _pairedDevices.value = emptyList()
            return
        }
        try {
            _pairedDevices.value = adapter.bondedDevices
                .filter { it.type != BluetoothDevice.DEVICE_TYPE_LE }
                .sortedBy { it.name ?: it.address }
        } catch (e: SecurityException) {
            _lastLog.value = "블루투스 기기 권한을 확인해 주세요"
            Log.e(TAG, "Cannot read paired Bluetooth devices", e)
        }
    }

    @SuppressLint("MissingPermission")
    fun connectToDevice(device: BluetoothDevice) {
        val proxy = hidDevice
        if (proxy == null) {
            _lastLog.value = "HID 준비 중입니다. 잠시 후 다시 선택해 주세요."
            return
        }
        try {
            _connectionState.value = ConnectionState.ProfileConnecting
            _lastLog.value = "${device.name ?: "선택한 기기"} 연결 요청 중…"
            val accepted = proxy.connect(device)
            if (!accepted) {
                _connectionState.value = ConnectionState.Error("기기 연결 요청이 거부되었습니다.")
                _lastLog.value = "연결 실패: 기기가 블루투스 페어링되어 있는지 확인해 주세요."
            }
        } catch (e: Exception) {
            Log.e(TAG, "HID host connection request failed", e)
            _connectionState.value = ConnectionState.Error("연결 오류: ${e.message}")
            _lastLog.value = "연결 실패: \${e.message}"
        }
    }

"""
    ms = ms.replace(anchor, methods + anchor, 1)

ms = ms.replace(
    '                _connectionState.value = ConnectionState.ProfileReady\n',
    '                _connectionState.value = ConnectionState.ProfileReady\n                refreshPairedDevices()\n',
    1
)
ms = ms.replace('"iPhone 연결 끊김"', '"블루투스 기기 연결 끊김"')
ms = ms.replace('"iPhone 연결 중…"', '"블루투스 기기 연결 중…"')
ms = ms.replace('"iPhone($name) 연결 성공!"', '"$name 연결 성공!"')
manager.write_text(ms, encoding="utf-8")

settings = Path("app/src/main/java/com/shortsremote/app/ui/SettingsScreen.kt")
ss = settings.read_text(encoding="utf-8")
if "val pairedDevices by hidManager.pairedDevices.collectAsState()" not in ss:
    anchor = "    val lastLog by hidManager.lastLog.collectAsState()"
    if anchor not in ss: raise SystemExit("Settings state anchor missing")
    ss = ss.replace(anchor, anchor + "\n    val pairedDevices by hidManager.pairedDevices.collectAsState()", 1)

if "페어링된 기기 선택" not in ss:
    anchor = """            Text(
                text = lastLog,"""
    if anchor not in ss: raise SystemExit("Settings log anchor missing")
    picker_ui = """            Text(
                text = "페어링된 기기 선택",
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = TextWhite
            )
            Button(
                onClick = { hidManager.refreshPairedDevices() },
                modifier = Modifier.fillMaxWidth(0.85f).height(34.dp),
                colors = ButtonDefaults.buttonColors(backgroundColor = DarkSurfaceElevated)
            ) { Text("기기 목록 새로고침", fontSize = 10.sp) }
            if (pairedDevices.isEmpty()) {
                Text(
                    text = "표시할 기기가 없습니다.\\n워치 블루투스 설정에서 아이폰/컴퓨터와 먼저 페어링하세요.",
                    fontSize = 9.sp,
                    color = TextMuted
                )
            } else {
                pairedDevices.take(4).forEach { device ->
                    Button(
                        onClick = { hidManager.connectToDevice(device) },
                        modifier = Modifier.fillMaxWidth(0.9f).height(32.dp),
                        colors = ButtonDefaults.buttonColors(backgroundColor = DarkSurfaceElevated)
                    ) { Text(device.name ?: device.address, fontSize = 10.sp, maxLines = 1) }
                }
            }

"""
    ss = ss.replace(anchor, picker_ui + anchor, 1)
settings.write_text(ss, encoding="utf-8")
print("Bluetooth paired-device picker patch applied.")
