"""Measure retained-frame VST with native and GPU landmark tile preprocessing.

The caller supplies the signed SpatialML service and both candidate lab APKs. The run holds one
devmux lease, refuses active calibration or screen recording, preserves the installed app/service,
camera calibration, debug property, output selection and external files, and restores them in
``finally``. It never clears data, uninstalls a package, starts calibration, or deletes recordings.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

from measure_face_outputs import Device, MUX, PACKAGE, SERIAL


SERVICE_PACKAGE = 'com.bytedance.pico.openmr.spatial'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signer_digest(path):
    apksigner = shutil.which('apksigner')
    if apksigner is None:
        candidates = sorted(
            (Path.home() / 'Library/Android/sdk/build-tools').glob('*/apksigner'),
            key=lambda candidate: tuple(
                int(part) if part.isdigit() else part
                for part in re.split(r'(\d+)', candidate.parent.name)
            ),
        )
        if not candidates:
            raise RuntimeError('apksigner is required to verify replacement certificates')
        apksigner = str(candidates[-1])
    result = subprocess.run(
        [apksigner, 'verify', '--print-certs', str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    match = re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]+)', result.stdout)
    if not match:
        raise RuntimeError('Could not read signer certificate from ' + str(path))
    return match[1].lower()


def measure(root, service, cpu_app, gpu_app, seconds):
    root.mkdir(parents=True, exist_ok=False)
    device = Device(root)
    manifest = {
        'windows': [],
        'originalAppRestored': False,
        'originalServiceRestored': False,
        'debugRestored': False,
        'leaseReleased': False,
        'settings': {
            'serial': SERIAL,
            'package': PACKAGE,
            'servicePackage': SERVICE_PACKAGE,
            'seconds': seconds,
            'outputMask': 7,
            'retainedVstPipeline': True,
            'inlineGeometry': True,
            'variants': {
                'cpu': 'native affine on 768x768 retained-frame RGB tile',
                'gpu': 'weightless GPU Resampler on 768x768 retained-frame RGB tile',
            },
        },
    }
    original_app = root / 'original-app.apk'
    original_service = root / 'original-service.apk'
    original_debug = None
    original_selection = None
    original_app_running = False
    app_started_for_preflight = False
    app_replace_attempted = False
    service_replace_attempted = False
    session_log = None
    session_stream = None
    before_files = {}

    def save():
        (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')

    def package_path(package):
        values = [line.removeprefix('package:') for line in device.adb('shell', 'pm', 'path', package).splitlines()]
        if len(values) != 1:
            raise RuntimeError(f'Expected one APK path for {package}, got {values}')
        return values[0]

    def package_hash(package):
        return device.adb('shell', 'sha256sum', package_path(package)).split()[0]

    def snapshot(label):
        state = device.snapshot(label)
        state['appApkSha256'] = package_hash(PACKAGE)
        state['serviceApkSha256'] = package_hash(SERVICE_PACKAGE)
        (device.data / (label + '.json')).write_text(json.dumps(state, indent=2) + '\n')
        return state

    def files(label):
        output = device.adb(
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
        (device.data / ('files-' + label + '.txt')).write_text(output)
        return {path: int(size) for size, path in (line.split('|', 1) for line in output.splitlines())}

    def private_calibration_digest():
        try:
            output = device.adb(
                'shell', 'run-as', PACKAGE, 'sha256sum', 'files/left-camera-to-head-v1.json'
            ).strip()
        except RuntimeError as error:
            if 'No such file or directory' in str(error):
                return None
            raise
        return output.split()[0]

    def install_service(apk, label):
        device.adb('shell', 'am', 'force-stop', PACKAGE)
        device.adb('shell', 'am', 'force-stop', SERVICE_PACKAGE)
        result = device.adb('install', '-r', str(apk))
        (device.data / (label + '-service-install.txt')).write_text(result)
        actual = package_hash(SERVICE_PACKAGE)
        if actual != digest(apk):
            raise RuntimeError(f'{label} service hash mismatch: {actual} != {digest(apk)}')
        return actual

    def install_app(apk, label):
        device.adb('shell', 'am', 'force-stop', PACKAGE)
        device.adb('shell', 'am', 'force-stop', SERVICE_PACKAGE)
        result = device.adb('install', '-r', str(apk))
        (device.data / (label + '-app-install.txt')).write_text(result)
        device.adb(
            'shell',
            'am',
            'start',
            '-n',
            PACKAGE + '/com.pico.spatial.ml.sample.facelandmarker.platform.MainActivity',
        )
        deadline = time.monotonic() + 60
        advancing = []
        while time.monotonic() < deadline:
            try:
                state = device.idle()
            except RuntimeError as error:
                if 'Lab did not answer' in str(error):
                    time.sleep(2)
                    continue
                raise
            print(label, 'frame', state['frame'], 'face', state['hasFace'], 'stopped', state['stopped'], flush=True)
            if state['stopped']:
                raise RuntimeError(state['message'])
            if state['frame'] >= 10 and (not advancing or state['frame'] > advancing[-1]):
                advancing.append(state['frame'])
            else:
                advancing = []
            if len(advancing) >= 3:
                break
            time.sleep(2)
        else:
            raise RuntimeError(label + ' did not supply advancing frames')
        device.command('outputs', 7)
        state = snapshot(label)
        if state['appApkSha256'] != digest(apk):
            raise RuntimeError(label + ' app hash mismatch')
        return state

    def window(label, variant, debug):
        item = device.window(label, 7, seconds, debug)
        item['variant'] = variant
        manifest['windows'].append(item)
        save()
        device.pull_journal(item['session'], label)

    subprocess.run(
        [str(MUX), 'acquire', '-s', SERIAL, '--wait', '15', '--note', 'Retained-frame VST face benchmark'],
        check=True,
    )
    try:
        session_stream = (device.data / 'session-continuous.log').open('wb')
        session_log = subprocess.Popen(
            [str(MUX), 'adb', '-s', SERIAL, 'logcat', '-T', '1', '-v', 'threadtime', '-v', 'usec'],
            stdout=session_stream,
            stderr=subprocess.STDOUT,
        )
        processes = device.adb('shell', 'ps', '-A').splitlines()
        original_app_running = any(
            line.split() and line.split()[-1] == PACKAGE for line in processes
        )
        original_debug = device.adb('shell', 'getprop', 'debug.pico.spatialml.debug').strip()
        if not device.adb('shell', 'dumpsys', 'media_projection').strip().endswith('null'):
            raise RuntimeError('Recording active')
        installed_app_path = package_path(PACKAGE)
        installed_service_path = package_path(SERVICE_PACKAGE)
        if not installed_service_path.startswith('/data/app/'):
            raise RuntimeError(
                'Installed SpatialML service is not a replaceable data-app update: '
                + installed_service_path
            )
        manifest['originalPackagePaths'] = {
            'app': installed_app_path,
            'service': installed_service_path,
        }
        installed_app_hash = device.adb('shell', 'sha256sum', installed_app_path).split()[0]
        installed_service_hash = device.adb('shell', 'sha256sum', installed_service_path).split()[0]
        device.adb('pull', installed_app_path, str(original_app))
        device.adb('pull', installed_service_path, str(original_service))
        manifest['apkSha256'] = {
            'originalApp': digest(original_app),
            'originalService': digest(original_service),
            'candidateService': digest(service),
            'cpuApp': digest(cpu_app),
            'gpuApp': digest(gpu_app),
        }
        if installed_app_hash != digest(original_app):
            raise RuntimeError('Pulled original app differs from installed app')
        if installed_service_hash != digest(original_service):
            raise RuntimeError('Pulled original service differs from installed service')
        manifest['signerSha256'] = {
            'originalApp': signer_digest(original_app),
            'originalService': signer_digest(original_service),
            'candidateService': signer_digest(service),
            'cpuApp': signer_digest(cpu_app),
            'gpuApp': signer_digest(gpu_app),
        }
        if manifest['signerSha256']['candidateService'] != manifest['signerSha256']['originalService']:
            raise RuntimeError('Candidate and installed SpatialML services have different signers')
        for label in ('cpuApp', 'gpuApp'):
            if manifest['signerSha256'][label] != manifest['signerSha256']['originalApp']:
                raise RuntimeError(f'{label} and installed lab app have different signers')
        manifest['privateCalibrationBefore'] = private_calibration_digest()
        before_files = files('before')
        if not original_app_running:
            device.adb(
                'shell',
                'am',
                'start',
                '-n',
                PACKAGE + '/com.pico.spatial.ml.sample.facelandmarker.platform.MainActivity',
            )
            app_started_for_preflight = True
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    initial = device.idle()
                    break
                except RuntimeError as error:
                    if 'Lab did not answer' not in str(error):
                        raise
                    time.sleep(2)
            else:
                raise RuntimeError('Original lab app did not answer after preflight launch')
        else:
            initial = device.idle()
        original_selection = initial['requestedOutputMask']
        device.command('outputs', 7)
        device.ready(7, seconds=30)
        manifest['before'] = snapshot('before')
        save()

        device.prop('0')
        service_replace_attempted = True
        install_service(service, 'candidate')
        for label, apk in [('cpu', cpu_app), ('gpu', gpu_app)]:
            app_replace_attempted = True
            install_app(apk, label)
            window(label + '-normal', label, '0')
            window(label + '-trace', label, '1')
            device.prop('0')

        device.adb('shell', 'am', 'force-stop', PACKAGE)
        install_service(original_service, 'restored')
        manifest['originalServiceRestored'] = True
        install_app(original_app, 'restored')
        manifest['originalAppRestored'] = True
    except Exception as error:
        manifest['error'] = str(error)
        print('BENCHMARK ERROR', error, flush=True)
    finally:
        restoration_errors = []
        try:
            if (
                service_replace_attempted
                and original_service.is_file()
                and not manifest['originalServiceRestored']
            ):
                try:
                    install_service(original_service, 'service-restore-recovery')
                    manifest['originalServiceRestored'] = True
                except Exception as error:
                    restoration_errors.append('Service restore: ' + str(error))
            if app_replace_attempted and original_app.is_file() and not manifest['originalAppRestored']:
                try:
                    install_app(original_app, 'app-restore-recovery')
                    manifest['originalAppRestored'] = True
                except Exception as error:
                    restoration_errors.append('App restore: ' + str(error))
            if (
                original_app_running
                and service_replace_attempted
                and not app_replace_attempted
                and manifest['originalServiceRestored']
            ):
                try:
                    device.adb(
                        'shell',
                        'am',
                        'start',
                        '-n',
                        PACKAGE + '/com.pico.spatial.ml.sample.facelandmarker.platform.MainActivity',
                    )
                except Exception as error:
                    restoration_errors.append('Original running state restore: ' + str(error))
            if original_debug is not None:
                try:
                    device.prop(original_debug)
                    manifest['debugRestored'] = True
                except Exception as error:
                    restoration_errors.append('Debug restore: ' + str(error))
            app_is_original = not app_replace_attempted or manifest['originalAppRestored']
            if original_selection is not None and app_is_original:
                try:
                    device.command('outputs', original_selection)
                except Exception as error:
                    restoration_errors.append('Output selection restore: ' + str(error))
            if app_replace_attempted:
                try:
                    manifest['final'] = snapshot('final')
                    manifest['privateCalibrationAfter'] = private_calibration_digest()
                    manifest['privateCalibrationPreserved'] = (
                        manifest['privateCalibrationBefore'] == manifest['privateCalibrationAfter']
                    )
                    after_files = files('after')
                    manifest['existingExternalFilesPreserved'] = all(
                        path in after_files and after_files[path] >= size for path, size in before_files.items()
                    )
                    manifest['existingExternalFileCount'] = len(before_files)
                    manifest['finalAppHashVerified'] = package_hash(PACKAGE) == digest(original_app)
                    manifest['finalServiceHashVerified'] = package_hash(SERVICE_PACKAGE) == digest(original_service)
                    failed_checks = [
                        name
                        for name in (
                            'privateCalibrationPreserved',
                            'existingExternalFilesPreserved',
                            'finalAppHashVerified',
                            'finalServiceHashVerified',
                        )
                        if not manifest[name]
                    ]
                    if failed_checks:
                        raise RuntimeError('Failed preservation checks: ' + ', '.join(failed_checks))
                except Exception as error:
                    restoration_errors.append('Preservation check: ' + str(error))
            elif service_replace_attempted:
                try:
                    manifest['finalServiceHashVerified'] = (
                        package_hash(SERVICE_PACKAGE) == digest(original_service)
                    )
                    if not manifest['finalServiceHashVerified']:
                        raise RuntimeError('Original service hash was not restored')
                except Exception as error:
                    restoration_errors.append('Final service hash check: ' + str(error))
            if not original_app_running and app_is_original and (app_replace_attempted or app_started_for_preflight):
                try:
                    device.adb('shell', 'am', 'force-stop', PACKAGE)
                except Exception as error:
                    restoration_errors.append('Original stopped state restore: ' + str(error))
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
                    subprocess.run([str(MUX), 'release', '-s', SERIAL], check=False).returncode == 0
                )
                save()
    print(root, flush=True)
    return 1 if manifest.get('error') or manifest['restorationErrors'] else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--service-apk', type=Path, required=True)
    parser.add_argument('--cpu-apk', type=Path, required=True)
    parser.add_argument('--gpu-apk', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=30, choices=range(15, 46))
    arguments = parser.parse_args()
    for candidate in (arguments.service_apk, arguments.cpu_apk, arguments.gpu_apk):
        if not candidate.is_file():
            parser.error('Candidate artifact does not exist: ' + str(candidate))
    raise SystemExit(
        measure(
            arguments.output,
            arguments.service_apk,
            arguments.cpu_apk,
            arguments.gpu_apk,
            arguments.seconds,
        )
    )
