#!/usr/bin/env bash
# Local lab operations; pin the headset and coordinate through devmux.
set -euo pipefail
lab_root="$(cd "$(dirname "$0")/../.." && pwd)"
lab_serial="${ANDROID_SERIAL:-PB311XHGKC220141G}"
lab_package=com.pico.spatial.ml.sample.facelandmarker.registrationlab
lab_mux="${DEVMUX_BIN:-$HOME/.trae/skills/devmux/scripts/devmux}"
lab_adb() { "$lab_mux" adb -s "$lab_serial" "$@"; }
case "${1:-}" in
  install|restart)
    lab_apk="$lab_root/FaceRegistrationLabApp/build/outputs/apk/debug/registrationlab-1.0-debug.apk"
    if [[ "$1" == install ]]; then test -f "$lab_apk"; fi
    "$lab_mux" acquire -s "$lab_serial" --wait 15 --note 'Kotlin face registration lab install or restart'
    trap '"$lab_mux" release -s "$lab_serial"' EXIT
    lab_projection="$(lab_adb shell dumpsys media_projection)"
    [[ "$lab_projection" == *null ]] || {
      echo 'Stop the headset recording before installing or restarting the lab. Keep the recording.'
      exit 1
    }
    if lab_adb shell pidof "$lab_package" > /dev/null; then
      lab_status="$(lab_adb shell am broadcast -a "$lab_package.COMMAND" -p "$lab_package" --es command status)"
      printf '%s' "$lab_status" | python3 -c '
import base64, json, re, sys
match = re.search(r"FACE_LAB_V1:([A-Za-z0-9+/=]+)", sys.stdin.read())
if not match:
    sys.exit("Lab status is unavailable. Wait for startup or close the app, then retry.")
state = json.loads(base64.b64decode(match[1]))
if state.get("automatic", {}).get("active") or (state.get("locked") and not state.get("stopped")):
    sys.exit("Calibration or a profile operation is active. Finish or cancel it before restarting.")
'
    fi
    # Reusing a Spatial service process after GPU teardown can fail to allocate LiteRT buffers.
    # Stop both face clients and the installed service processes; APKs and app data are retained.
    lab_adb shell am force-stop com.pico.spatial.ml.sample.facelandmarker
    lab_adb shell am force-stop "$lab_package"
    lab_adb shell am force-stop com.bytedance.pico.openmr.spatial
    lab_adb shell am force-stop com.bytedance.pico.openmr
    if [[ "$1" == install ]]; then
      lab_adb install -r "$lab_apk"
      lab_adb shell pm grant "$lab_package" android.permission.CAMERA
    fi
    lab_adb shell am start -n "$lab_package/com.pico.spatial.ml.sample.facelandmarker.platform.MainActivity"
    ;;
  pull)
    lab_destination="${2:-$lab_root/artifacts/facelandmarker/registration-lab/captures}"
    mkdir -p "$lab_destination"
    lab_adb pull "/sdcard/Android/data/$lab_package/files/RegistrationLab" "$lab_destination/"
    ;;
  profiles)
    lab_destination="${2:-$lab_root/artifacts/facelandmarker/registration-lab/profiles}"
    mkdir -p "$lab_destination"
    lab_adb pull "/sdcard/Android/data/$lab_package/files/RegistrationLabProfiles" "$lab_destination/"
    ;;
  logs)
    mkdir -p "$lab_root/artifacts/facelandmarker/registration-lab"
    lab_adb logcat -d -t 4000 > "$lab_root/artifacts/facelandmarker/registration-lab/device-logcat.txt"
    ;;
  save|step|mode|mesh|save_values|load_values|reset_c|tools|auto_start|auto_check|auto_geometry|geometry_check|auto_roll|auto_cancel|pose_correction)
    # The app receiver requires Android DUMP, which adb shell holds.
    lab_adb shell am broadcast -a "$lab_package.COMMAND" -p "$lab_package" --es command "$1"
    ;;
  set)
    case "${2:-}" in fx|fy|cx|cy) ;; *) echo 'Expected fx, fy, cx or cy'; exit 2 ;; esac
    [[ "${3:-}" =~ ^[0-9]+([.][0-9]+)?$ ]] || { echo 'Expected a nonnegative pixel value'; exit 2; }
    lab_adb shell am broadcast -a "$lab_package.COMMAND" -p "$lab_package" --es command set --es parameter "$2" --es value "$3"
    ;;
  status)
    "$lab_mux" status
    lab_adb shell getprop ro.build.fingerprint
    lab_adb shell pidof "$lab_package"
    ;;
  *) echo 'Usage: registration_lab_device.sh {install|restart|pull [directory]|profiles [directory]|logs|status|save|step|mode|mesh|save_values|load_values|reset_c|tools|auto_check|auto_start|geometry_check|auto_geometry|auto_roll|auto_cancel|pose_correction|set fx|fy|cx|cy value}'; exit 2 ;;
esac
