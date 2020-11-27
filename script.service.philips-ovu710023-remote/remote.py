import json
import os
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
addon_dir = xbmc.translatePath(settings.getAddonInfo('path'))


class Listener(xbmc.Monitor):

    _config = None
    _listeners = []
    _last_action_ts = 0
    _last_scan_inputs = set()

    def __init__(self):

        xbmc.Monitor.__init__(self)

        self._load_config()

    def _load_config(self):
        data = open(os.path.join(addon_dir, "resources",
                                 "remote.json"), "r").read()
        self._config = json.loads(data)

    def refresh(self):

        def _scan_inputs():

            _current = set(filter(lambda e: e.startswith(
                "event"), os.listdir("/dev/input")))
            _new = _current - self._last_scan_inputs
            _old = self._last_scan_inputs - _current
            self._last_scan_inputs = _current
            return _old, _new

        def _evtest_find_devices():

            p1 = subprocess.Popen(["echo", "-e", "\n"], stdout=subprocess.PIPE)
            p2 = subprocess.Popen(["evtest"], stdin=p1.stdout,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p1.stdout.close()
            out, err = p2.communicate()

            devices = {}
            for line in err.decode("utf-8").split("\n"):
                m = re.search(r"(/dev/input/event[0-9]+):\s+(.+)", line)
                if m:
                    devices[m.group(2)] = m.group(1)

            return devices

        def _has_listener(_i):
            for _l in self._listeners:
                if _l["name"] == _i:
                    return True
            return False

        old, new = _scan_inputs()

        if len(old) > 0:
            listeners_to_shutdown = list(
                filter(lambda _l: _l["path"].split("/")[-1] in old, self._listeners))
            self.shutdown(listeners_to_shutdown)

        if len(new) > 0:
            _input_devices = _evtest_find_devices()
            for _input in self._config:
                if _input in _input_devices and not _has_listener(_input):
                    self._start(_input, _input_devices[_input])
                    time.sleep(0.2)

    def shutdown(self, listeners_to_shutdown=_listeners):

        shutted_down_listeners = []
        for l in listeners_to_shutdown:
            l["subprocess"].kill()
            shutted_down_listeners.append(l)

        for k in shutted_down_listeners:
            xbmc.log("remote %s" % k["path"], xbmc.LOGNOTICE)
            self._listeners.remove(k)

    def _start(self, input_name, path):

        listener = {
            "name": input_name,
            "path": path
        }

        _l = threading.Thread(target=self._listen, args=(listener,))
        _l.daemon = True
        _l.start()

        xbmc.log("[Philips remote] start listener for %s at %s" %
                 (listener["name"], listener["path"]), xbmc.LOGNOTICE)

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

        proc = subprocess.Popen(
            ["evtest", "--grab", listener["path"]], stdout=subprocess.PIPE)

        listener["subprocess"] = proc

        xbmc.log("[Philips remote] listener for %s at %s starts listening..." %
                 (listener["name"], listener["path"]), xbmc.LOGDEBUG)

        sequence, modifiers = [], 0
        for line in iter(proc.stdout.readline, ""):

            event = _parse_event(line)

            if event:
                xbmc.log("[Philips remote] incoming raw event at %s (%s): %s, %s" %
                         (listener["name"], listener["path"], event["key_state"], event["key_code"]), xbmc.LOGDEBUG)

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
                 (listener["name"], listener["path"]), xbmc.LOGNOTICE)

    def _apply_sequence(self, sequence):

        def _match_sequence(sequence):

            if sequence == []:
                return None, None

            for known_inputs in self._config:
                for definition in self._config[known_inputs]:
                    if self._config[known_inputs][definition]["seq"] == sequence:
                        return definition, self._config[known_inputs][definition]["action"]

            return None, None

        definition, action = _match_sequence(sequence)
        if definition:
            xbmc.log("[Philips remote] found action: %s --> %s" %
                     (definition, action), xbmc.LOGDEBUG)
            if not self._turn_display_on():
                xbmc.executebuiltin(action)
            return True

        return False

    def _turn_display_on(self):

        current_time = time.time()
        if self._last_action_ts + 299 > current_time:
            return False

        ps = subprocess.Popen(
            ["xset", "-q"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = ps.communicate()
        self._last_action_ts = current_time
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
