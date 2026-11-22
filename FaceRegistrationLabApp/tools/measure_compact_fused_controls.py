"""Measure only the compact adjacent-VST and fused-control candidate.

Requires a connected PB311XHGKC220141G and a sustained face in view. The driver
backs up and restores the installed lab APK, debug property and output selection.
It never starts calibration, clears data, uninstalls an app, changes camera K,
deletes files or starts a recording. The opt-in service reset stops both face
apps and the installed OpenMR service packages before candidate/restored launch.
"""

import argparse
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import time

from measure_face_outputs import Device, MUX, PACKAGE, SERIAL


MAIN_PACKAGE = 'com.pico.spatial.ml.sample.facelandmarker'
OPENMR_PACKAGES = (
    'com.bytedance.pico.openmr.spatial',
    'com.bytedance.pico.openmr',
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(root, candidate, seconds, reset_openmr_services, window_mode):
    root.mkdir(parents=True, exist_ok=False)
    device = Device(root)
    manifest = {
        'windows': [],
        'originalRestored': False,
        'debugRestored': False,
        'selectionRestored': False,
        'leaseReleased': False,
        'settings': {
            'pipeline': 'compact-adjacent-vst-fused-controls',
            'preprocessing': 'gpu-rgb-first',
            'outputMask': 7,
            'seconds': seconds,
            'serial': SERIAL,
            'package': PACKAGE,
            'resetOpenMrServices': reset_openmr_services,
            'windowMode': window_mode,
        },
    }
    original = root / 'original.apk'
    original_debug = None
    selection = None
    replaced = False
    before_files = None
    session_stream = None
    session_log = None

    def save():
        (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')

    def snapshot(label):
        state = device.snapshot(label)
        path = device.adb('shell', 'pm', 'path', PACKAGE).strip().removeprefix('package:')
        state['apkSha256'] = device.adb('shell', 'sha256sum', path).split()[0]
        (device.data / (label + '.json')).write_text(json.dumps(state, indent=2) + '\n')
        return state

    def files(label):
        data = device.adb(
            'shell',
            'find',
            f'/sdcard/Android/data/{PACKAGE}/files',
            '-type',
            'f',
            '-exec',
            'stat',
            '-c',
            '"%s|%n"',
            '{}',
            '\\;',
        )
        (device.data / ('files-' + label + '.txt')).write_text(data)
        return {path: int(size) for size, path in (line.split('|', 1) for line in data.splitlines())}

    def start_and_wait(label):
        device.adb(
            'shell',
            'am',
            'start',
            '-n',
            PACKAGE + '/com.pico.spatial.ml.sample.facelandmarker.platform.MainActivity',
        )
        deadline = time.monotonic() + 60
        seen = []
        while time.monotonic() < deadline:
            try:
                state = device.idle()
            except RuntimeError as error:
                if 'Lab did not answer' in str(error):
                    time.sleep(2)
                    continue
                raise
            print(
                label,
                'frame',
                state['frame'],
                'face',
                state['hasFace'],
                'stopped',
                state['stopped'],
                flush=True,
            )
            if state['stopped']:
                raise RuntimeError(state['message'])
            if state['frame'] >= 10 and (not seen or state['frame'] > seen[-1]):
                seen.append(state['frame'])
            else:
                seen = []
            if len(seen) >= 3:
                return state
            time.sleep(2)
        raise RuntimeError(label + ' did not supply advancing frames')

    def process_pids(packages):
        wanted = set(packages)
        processes = {}
        for line in device.adb('shell', 'ps', '-A').splitlines()[1:]:
            fields = line.split()
            if fields and fields[-1] in wanted:
                processes[fields[-1]] = int(fields[1])
        return processes

    def reset_apps_and_services(label):
        packages = (PACKAGE, MAIN_PACKAGE, *OPENMR_PACKAGES)
        item = {'label': label, 'before': process_pids(packages)}
        for package in packages:
            device.adb('shell', 'am', 'force-stop', package)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            item['after'] = process_pids(packages)
            if not item['after']:
                break
            time.sleep(.5)
        else:
            raise RuntimeError(
                label + ' did not stop app/OpenMR processes: ' + str(item['after'])
            )
        manifest.setdefault('serviceResets', []).append(item)
        save()

    def install(apk, label):
        if reset_openmr_services:
            reset_apps_and_services(label)
        else:
            device.adb('shell', 'am', 'force-stop', PACKAGE)
            device.adb('shell', 'am', 'force-stop', MAIN_PACKAGE)
        time.sleep(2)
        (device.data / (label + '-install.txt')).write_text(
            device.adb('install', '-r', str(apk))
        )
        device.adb('shell', 'pm', 'grant', PACKAGE, 'android.permission.CAMERA')
        state = start_and_wait(label)
        device.command('outputs', 7)
        recorded = snapshot(label)
        if recorded['apkSha256'] != digest(apk):
            raise RuntimeError(label + ' installed APK hash mismatch')
        return state

    def ready_for_window(label):
        samples = []
        face_frames = []
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = device.idle()
            samples.append(state)
            (device.data / (label + '-ready.json')).write_text(
                json.dumps(samples, indent=2) + '\n'
            )
            if state['stopped']:
                raise RuntimeError(state['message'])
            if (
                state.get('appliedOutputMask') == 7
                and state['hasFace']
                and state['frameAgeSeconds'] < 1
                and (not face_frames or state['frame'] > face_frames[-1])
            ):
                face_frames.append(state['frame'])
            if len(face_frames) >= 3:
                return state
            print(
                'waiting',
                label,
                'frame',
                state['frame'],
                'face',
                state['hasFace'],
                'positive samples',
                len(face_frames),
                flush=True,
            )
            time.sleep(2)
        raise RuntimeError(label + ' did not produce three face-positive advancing samples')

    def window(label, debug):
        device.command('outputs', 7)
        ready_for_window(label)
        device.prop(debug)
        time.sleep(1)
        first = device.idle()
        started = time.monotonic()
        device.capture(label, seconds)
        last = device.idle()
        if last['stopped']:
            raise RuntimeError('Camera stopped in ' + label)
        item = {
            'label': label,
            'mask': 7,
            'debug': debug,
            'startFrame': first['frame'],
            'endFrame': last['frame'],
            'session': first['timeline']['session'],
            'clientPid': int(device.adb('shell', 'pidof', PACKAGE).strip()),
            'elapsedHostSeconds': time.monotonic() - started,
            'startStatus': first,
            'endStatus': last,
            'log': label + '.log',
        }
        item['variant'] = 'compact-fused-controls'
        manifest['windows'].append(item)
        save()
        print(
            label,
            'frames',
            item['startFrame'],
            item['endFrame'],
            'face',
            first['hasFace'],
            last['hasFace'],
            flush=True,
        )
        device.pull_journal(item['session'], label)

    subprocess.run(
        [
            str(MUX),
            'acquire',
            '-s',
            SERIAL,
            '--wait',
            '30',
            '--note',
            'Compact adjacent-VST fused-control face benchmark',
        ],
        check=True,
    )
    try:
        session_stream = (device.data / 'session-continuous.log').open('wb')
        session_log = subprocess.Popen(
            [
                str(MUX),
                'adb',
                '-s',
                SERIAL,
                'logcat',
                '-T',
                '1',
                '-v',
                'threadtime',
                '-v',
                'usec',
            ],
            stdout=session_stream,
            stderr=subprocess.STDOUT,
        )
        original_debug = device.adb(
            'shell', 'getprop', 'debug.pico.spatialml.debug'
        ).strip()
        start_and_wait('original')
        initial = device.idle()
        selection = initial['requestedOutputMask']
        device.command('outputs', 7)
        device.ready(7, seconds=45)
        path = device.adb('shell', 'pm', 'path', PACKAGE).strip().removeprefix('package:')
        device.adb('pull', path, str(original))
        manifest['before'] = snapshot('before')
        if manifest['before']['apkSha256'] != digest(original):
            raise RuntimeError('Original APK backup hash mismatch')
        manifest['apkSha256'] = {
            'original': digest(original),
            'candidate': digest(candidate),
        }
        manifest['privateCalibrationBefore'] = device.adb(
            'shell',
            'run-as',
            PACKAGE,
            'sha256sum',
            'files/left-camera-to-head-v1.json',
        ).strip()
        before_files = files('before')
        save()

        device.prop('1')
        replaced = True
        install(candidate, 'candidate')
        if window_mode in ('both', 'normal'):
            window('fused-normal', '0')
        if window_mode in ('both', 'trace'):
            window('fused-trace', '1')

        device.prop('0')
        install(original, 'restored')
        manifest['originalRestored'] = True
    except Exception as error:
        manifest['error'] = str(error)
        print('BENCHMARK ERROR', error, flush=True)
    finally:
        restoration_errors = []
        try:
            if replaced and not manifest['originalRestored']:
                try:
                    install(original, 'restore-recovery')
                    manifest['originalRestored'] = True
                except Exception as error:
                    restoration_errors.append('APK restore: ' + str(error))
            if original_debug is not None:
                try:
                    device.prop(original_debug)
                    manifest['debugRestored'] = True
                except Exception as error:
                    restoration_errors.append('Debug restore: ' + str(error))
            if selection is not None:
                try:
                    device.command('outputs', selection)
                    manifest['selectionRestored'] = True
                except Exception as error:
                    restoration_errors.append('Selection restore: ' + str(error))
            if replaced:
                try:
                    manifest['final'] = snapshot('final')
                    manifest['privateCalibrationAfter'] = device.adb(
                        'shell',
                        'run-as',
                        PACKAGE,
                        'sha256sum',
                        'files/left-camera-to-head-v1.json',
                    ).strip()
                    manifest['privateCalibrationPreserved'] = (
                        manifest['privateCalibrationBefore']
                        == manifest['privateCalibrationAfter']
                    )
                    after_files = files('after')
                    manifest['existingExternalFilesPreserved'] = all(
                        path in after_files and after_files[path] >= size
                        for path, size in before_files.items()
                    )
                    manifest['existingExternalFileCount'] = len(before_files)
                except Exception as error:
                    restoration_errors.append('Preservation check: ' + str(error))
        finally:
            manifest['restorationErrors'] = restoration_errors
            try:
                if session_log is not None and session_log.poll() is None:
                    session_log.send_signal(signal.SIGINT)
                    try:
                        session_log.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        session_log.kill()
                        session_log.wait(timeout=5)
                        restoration_errors.append('Continuous log did not exit on interrupt')
            finally:
                if session_stream is not None:
                    session_stream.close()
                manifest['leaseReleased'] = (
                    subprocess.run([str(MUX), 'release', '-s', SERIAL]).returncode == 0
                )
                save()
    print(root, flush=True)
    return 1 if manifest.get('error') or manifest['restorationErrors'] else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate-apk', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=30, choices=range(20, 46))
    parser.add_argument(
        '--reset-openmr-services',
        action='store_true',
        help='Stop both face apps and the Spatial/XR OpenMR packages before each install',
    )
    parser.add_argument(
        '--window',
        choices=('both', 'normal', 'trace'),
        default='both',
        help='Collect both timing windows or only the selected missing window',
    )
    args = parser.parse_args()
    if not args.candidate_apk.is_file():
        parser.error('Candidate APK does not exist')
    raise SystemExit(
        measure(
            args.output,
            args.candidate_apk,
            args.seconds,
            args.reset_openmr_services,
            args.window,
        )
    )
