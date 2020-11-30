import json
import os
import platform
import re
import threading
import time
import subprocess
import xbmc
import xbmcaddon

KEY_STATE_UP = 0
KEY_STATE_DOWN = 1
KEY_STATE_HOLD = 2

MODIFIER_KEYS = {
    "KEY_LEFTCTRL": 29,
    "KEY_LEFTALT": 56,
    "KEY_LEFTSHIFT": 42,
    "KEY_RIGHTSHIFT": 54,
    "KEY_RIGHTCTRL": 97,
    "KEY_RIGHTALT": 100
}

__PLUGIN_ID__ = "script.service.philips-ovu710023-remote"
settings = xbmcaddon.Addon(id=__PLUGIN_ID__)
addon_dir = xbmc.translatePath(settings.getAddonInfo("path"))


class Listener(xbmc.Monitor):

    _config = None
    _listeners = []
    _last_action_ts = 0
    _prev_devices = set()

    def __init__(self):

        xbmc.Monitor.__init__(self)

        data = open(os.path.join(addon_dir, "resources",
                                 "remote.json"), "r").read()
        self._config = json.loads(data)

    def refresh(self):

        def _get_devices():

            _devices = {}
            _name, _handler = None, None

            data = open("/proc/bus/input/devices", "r")
            for _line in data.readlines():
                m = re.search(r"[NH]: (Name|Handlers)=(.+)", _line)
                if m and m.group(1) == "Name":
                    _name = m.group(2)[1:-1]
                elif m and m.group(1) == "Handlers":
                    m = re.search(r".*(event\d+).*", m.group(2))
                    _handler = m.group(1) if m else None

                if _name and _handler:
                    _devices[_name] = _handler
                    _name, _handler = None, None

            return _devices

        def _has_listener(name):
            for listener in self._listeners:
                if listener["name"] == name:
                    return True
            return False

        devices = _get_devices()
        added_handlers = set(devices) - set(self._prev_devices)
        removed_handlers = set(self._prev_devices) - set(devices)
        self._prev_devices = devices

        if len(removed_handlers) > 0:
            listeners_to_shutdown = list(
                filter(lambda _l: _l["handler"] in removed_handlers, self._listeners))
            self.shutdown(listeners_to_shutdown)

        if len(added_handlers) > 0:
            for name in self._config:
                if name in devices and not _has_listener(name):
                    self._start(name, devices[name])
                    time.sleep(0.2)

    def shutdown(self, listeners_to_shutdown=_listeners):

        shutted_down_listeners = []
        for l in listeners_to_shutdown:
            l["subprocess"].kill()
            shutted_down_listeners.append(l)

        for k in shutted_down_listeners:
            self._listeners.remove(k)

    def _start(self, name, handler):

        listener = {
            "name": name,
            "handler": handler
        }

        _l = threading.Thread(target=self._listen, args=(listener,))
        _l.daemon = True
        _l.start()

        xbmc.log("[Philips remote] start listener for %s at %s" %
                 (name, handler), xbmc.LOGNOTICE)

        self._listeners.append(listener)

        return listener

    def _listen(self, listener):

        def _parse_event(line):

            xbmc.log(line, xbmc.LOGDEBUG)

            m = re.search(
                r"type 1 \(EV_KEY\), code ([0-9]+) \(([^\)]+)\), value ([012])", line)
            return {
                "state": int(m.group(3)),
                "key_state": ("UP", "DOWN", "HOLD")[int(m.group(3))],
                "scan_code": int(m.group(1)),
                "key_code": m.group(2)
            } if m else None

        def _get_evtest():

            if platform.machine().startswith("arm"):
                return os.path.join(addon_dir, "lib", "evtest_armhf")
            elif platform.machine() == "x86_64":
                return os.path.join(addon_dir, "lib", "evtest_x86_64")
            elif platform.machine() == "i386":
                return os.path.join(addon_dir, "lib", "evtest_i386")
            else:
                return "evtest"

        proc = subprocess.Popen(
            [_get_evtest(), "--grab", "/dev/input/%s" % listener["handler"]], stdout=subprocess.PIPE)

        listener["subprocess"] = proc

        xbmc.log("[Philips remote] listener for %s at %s starts listening..." %
                 (listener["name"], listener["handler"]), xbmc.LOGDEBUG)

        sequence, modifiers = [], 0
        for line in iter(proc.stdout.readline, ""):

            event = _parse_event(line)

            if event:
                xbmc.log("[Philips remote] incoming raw event at %s (%s): %s, %s" %
                         (listener["name"], listener["handler"], event["key_state"], event["key_code"]), xbmc.LOGDEBUG)

                if event["key_code"] in MODIFIER_KEYS:
                    if event["state"] == KEY_STATE_DOWN:
                        modifiers += 1
                    elif event["state"] == KEY_STATE_UP:
                        modifiers -= 1

                if event["state"] == KEY_STATE_DOWN:
                    sequence.append(event["scan_code"])
                elif event["state"] == KEY_STATE_HOLD:
                    self._apply_sequence([event["scan_code"]])

                if modifiers <= 0 and self._apply_sequence(sequence):
                    sequence, modifiers = [], 0

        proc.stdout.close()
        proc.kill()

        xbmc.log("[Philips remote] listener for %s at %s shutted down" %
                 (listener["name"], listener["handler"]), xbmc.LOGNOTICE)

    def _apply_sequence(self, sequence):

        def _match_sequence(sequence):

            if sequence == []:
                return None, None

            for name in self._config:
                for key in self._config[name]:
                    if self._config[name][key]["seq"] == sequence:
                        return key, self._config[name][key]["action"]

            return None, None

        key, action = _match_sequence(sequence)
        if key:
            xbmc.log("[Philips remote] found action: %s --> %s" %
                     (key, action), xbmc.LOGDEBUG)
            if not self._turn_display_on():
                xbmc.executebuiltin(action)
            return True

        return False

    def _turn_display_on(self):

        now = time.time()
        if self._last_action_ts + 299 > now:
            return False

        ps = subprocess.Popen(
            ["xset", "-q"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = ps.communicate()
        self._last_action_ts = now
        if not re.search("Monitor is On", stdout):
            xbmc.log("[Philips remote] turn monitor on", xbmc.LOGNOTICE)
            subprocess.call(["xset", "dpms", "force", "on"])
            return True
        else:
            return False


if __name__ == "__main__":

    xbmc.log("[Philips remote] Service is starting", xbmc.LOGNOTICE)
    listener = Listener()

    while not listener.abortRequested():

        listener.refresh()
        if listener.waitForAbort(10):
            pass

    xbmc.log("[Philips remote] stopping service", xbmc.LOGNOTICE)
    listener.shutdown()
    xbmc.log("[Philips remote] Service stopped.", xbmc.LOGNOTICE)
