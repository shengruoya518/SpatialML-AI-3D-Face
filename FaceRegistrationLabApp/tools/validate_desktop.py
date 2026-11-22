"""Exercise the local HTTP bridge and browser controls against a deterministic fake headset.

Browser mode requires playwright and a local Chrome binary. This does not replace
live adb verification against the actual APK.
"""
import argparse
import base64
import copy
import http.client
import json
from pathlib import Path
import threading

from calibration_desktop import Server, command_args, decode_response


class FakeHeadset:
    serial = 'TEST-HEADSET'

    def __init__(self):
        self.calls = []
        self.offline = False
        self.state = dict(schema=1, accepted=True, values=dict(fx=1746.47, fy=1746.47, cx=1623.5, cy=1231.5),
                          mode=4, modeLabel='Custom: adjustable', revision=0, appliedMode=4, appliedRevision=0,
                          frame=20, frameAgeSeconds=.1, hasFace=True, locked=False, stopped=False,
                          trialsAvailable=True, profileBusy=False, savedProfileAvailable=True,
                          message='Ready', profileMessage='Test profile')
        self.state['appliedValues'] = dict(self.state['values'])
        self.state['automatic'] = dict(active=False, phase='IDLE', trial=0, total=0, saved=0, message='Ready')
        self.saved = dict(self.state['values'])
        self.automatic_original = None

    def send(self, request):
        command_args(request)
        if self.offline:
            raise RuntimeError('Test USB disconnected')
        self.calls.append(copy.deepcopy(request))
        command = request['command']
        if command in ('auto_check', 'auto_start'):
            assert not self.state['automatic']['active']
            self.automatic_original = dict(self.state['values'])
            self.state['automatic'].update(active=True, phase='COUNTDOWN', trial=0,
                                           total=1 if command == 'auto_check' else 28, saved=0,
                                           message='Start Spatial recording.')
        elif command == 'auto_cancel':
            self.state['values'] = dict(self.automatic_original)
            self.state['automatic'].update(active=False, phase='CANCELLED', message='Starting values restored.')
            self.state['revision'] += 1
        elif command != 'status':
            assert not self.state['automatic']['active'], 'Browser sent an edit during automatic capture'
        if command == 'set':
            self.state['values'][request['parameter']] = request['value']
            self.state['revision'] += 1
        elif command == 'save_values':
            self.saved = dict(self.state['values'])
            self.state['profileMessage'] = 'Calibration saved on this headset.'
        elif command in ('load_values', 'reset_c'):
            self.state['values'] = dict(self.saved if command == 'load_values' else dict(fx=1746.47,fy=1746.47,cx=1623.5,cy=1231.5))
            self.state['revision'] += 1
        return copy.deepcopy(self.state)


def run(browser, output):
    for request in [dict(command='erase'), dict(command='set', parameter='fx', value='$(id)'),
                    dict(command='set',parameter='cy',value=float('nan')),
                    dict(command='set',parameter='fx',value=0), dict(command='set',parameter='cx',value=True)]:
        try:
            command_args(request)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid bridge command accepted')
    fake = FakeHeadset()
    encoded = base64.b64encode(json.dumps(fake.state).encode()).decode()
    assert decode_response('Broadcast completed: result=0, data="FACE_LAB_V1:'+encoded+'"') == fake.state
    try:
        decode_response('Broadcast completed: result=0')
    except RuntimeError:
        pass
    else:
        raise AssertionError('Missing app receiver was accepted')
    server = Server(('127.0.0.1', 0), fake)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.05), daemon=True)
    thread.start()
    try:
        def request(method, path, data=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            connection.request(method, path, json.dumps(data) if data is not None else None, headers or {})
            response = connection.getresponse()
            result = response.status, response.read()
            connection.close()
            return result
        assert request('GET', '/')[0] == 200
        assert request('POST', '/api/command', dict(command='reset_c'))[0] == 403
        headers = {'Origin':server.origin, 'X-Calibrate-Token':server.token, 'Content-Type':'application/json'}
        assert request('POST', '/api/command', dict(command='status'), headers)[0] == 200
        assert request('POST', '/api/command', dict(command='set',parameter='fy',value=-1), headers)[0] == 400
        assert request('POST', '/api/command', dict(command='set',parameter='cy',value=1200.5), headers)[0] == 200
        assert fake.state['values']['cy'] == 1200.5
        for command in ('auto_check', 'auto_cancel', 'auto_start', 'auto_cancel'):
            assert request('POST', '/api/command', dict(command=command), headers)[0] == 200
        assert fake.state['automatic']['phase'] == 'CANCELLED'
        fake.offline = True
        assert request('POST','/api/command',dict(command='status'),headers)[0] == 503
        fake.offline = False
        print('PASS: validation, ordered-broadcast decoding, HTTP command delivery, origin/token checks and disconnect reporting')
        if browser:
            from playwright.sync_api import sync_playwright, expect
            with sync_playwright() as p:
                chrome = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True)
                page = chrome.new_page(viewport=dict(width=1180, height=1000))
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(server.origin)
                page.get_by_text('Headset connected', exact=True).wait_for()
                fx = page.get_by_role('spinbutton', name='Horizontal focal length in pixels')
                fx.fill('1701.25')
                expect(page.locator(".requested").first).to_have_text("1701.25")
                # Requested and effective values must remain distinguishable while waiting for a frame.
                assert page.locator('.applied').first.inner_text() == '1746.47'
                page.get_by_role('button',name='Increase fx',exact=True).click()
                expect(page.locator(".requested").first).to_have_text("1706.25")
                fx.press('ArrowDown')
                expect(page.locator(".requested").first).to_have_text("1701.25")
                fx.press('Shift+ArrowUp')
                expect(page.locator(".requested").first).to_have_text("1751.25")
                page.get_by_role('slider',name='Horizontal focal length slider').evaluate("e => { for (let n=1600;n<=1640;n+=10) { e.value=n; e.dispatchEvent(new Event('input',{bubbles:true})); } }")
                page.get_by_role('button',name='Save on headset',exact=True).click()
                page.get_by_text('Calibration saved on this headset.',exact=True).wait_for()
                assert fake.saved['fx'] == 1640
                # Move focus away, then an external headset edit must appear in the local controls.
                page.locator('h1').click()
                fake.state['values']['fx'] = 1666.5
                expect(fx).to_have_value("1666.50")
                fake.offline = True
                page.get_by_text('Disconnected',exact=True).wait_for()
                assert fx.is_disabled()
                fake.state['values']['fx'] = 1680
                fake.offline = False
                page.get_by_text('Headset connected',exact=True).wait_for()
                expect(fx).to_have_value("1680.00")
                assert fake.state['values']['fx'] == 1680
                # Pending edits must reach the headset before the sequence records starting values.
                fx.fill('1690.5')
                page.get_by_role('button', name='Capture one check sample', exact=True).click()
                expect(page.locator('#auto-status')).to_contain_text('COUNTDOWN')
                assert fake.automatic_original['fx'] == 1690.5
                assert fake.state['automatic']['total'] == 1
                expect(fx).to_be_disabled()
                expect(page.locator('#save')).to_be_disabled()
                expect(page.locator('#auto-start')).to_be_disabled()
                # Export locking must leave Cancel available; completion of the export unlocks inputs.
                fake.state['locked'] = True
                fake.state['automatic'].update(phase='MARKED', trial=1, saved=1)
                expect(page.locator('#auto-status')).to_contain_text('MARKED')
                expect(page.locator('#auto-cancel')).to_be_enabled()
                page.locator('#auto-cancel').click()
                expect(page.locator('#auto-status')).to_contain_text('CANCELLED')
                expect(fx).to_be_disabled()
                fake.state['locked'] = False
                expect(fx).to_be_enabled()
                expect(fx).to_have_value('1690.50')
                assert fake.saved['fx'] == 1640  # trials never save a profile
                page.locator('#auto-start').click()
                expect(page.locator('#auto-status')).to_contain_text('0/28')
                fake.offline = True
                page.get_by_text('Disconnected', exact=True).wait_for()
                expect(page.locator('#auto-cancel')).to_be_disabled()
                fake.offline = False
                page.get_by_text('Headset connected', exact=True).wait_for()
                expect(page.locator('#auto-status')).to_contain_text('COUNTDOWN')
                expect(fx).to_be_disabled()
                page.locator('#auto-cancel').click()
                expect(page.locator('#auto-status')).to_contain_text('CANCELLED')
                # An older app remains usable for manual controls but cannot start the new protocol.
                automatic = fake.state.pop('automatic')
                expect(page.locator('#auto-status')).to_contain_text('Install the automatic-capture update')
                expect(page.locator('#auto-check')).to_be_disabled()
                expect(page.locator('#auto-start')).to_be_disabled()
                fake.state['automatic'] = automatic
                expect(page.locator('#auto-check')).to_be_enabled()
                output.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(output/'desktop-ui.png'),full_page=True)
                assert not errors, errors
                chrome.close()
                print('PASS: browser numeric/keyboard/slider input; coalescing; save ordering; readback distinction; external edits; disconnect/reconnect; no JS exceptions')
                print('PASS: automatic command delivery, edit ordering, active lock, cancellation during export, restored values, reconnect and old-app compatibility')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('artifacts/facelandmarker/registration-lab/desktop-validation'))
    args=parser.parse_args()
    run(args.browser,args.output)
