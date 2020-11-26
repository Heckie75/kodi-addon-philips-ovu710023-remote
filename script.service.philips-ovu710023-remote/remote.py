import re
import threading
import time
import subprocess
import xbmc

__PLUGIN_ID__ = "script.service.philips-ovu710023-remote"

PHILIPS_OVU710023_KEYBOARD = "PHILIPS OVU710023 Keyboard"
PHILIPS_OVU710023_SYSTEM_CONTROL = "PHILIPS OVU710023 System Control"
PHILIPS_OVU710023_CONSUMER_CONTROL = "PHILIPS OVU710023 Consumer Control"
PHILIPS_OVU710023_MOUSE = "PHILIPS OVU710023 Mouse"

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

INPUTS = {
    PHILIPS_OVU710023_KEYBOARD: {
        "KEY_ESC": [1],
        "KEY_ENTER": [28],
        "KEY_UP": [103],
        "KEY_LEFT": [105],
        "KEY_RIGHT": [106],
        "KEY_DOWN": [108],
        "PHILIPS_OVU710023_KEY_0": [56, 75, 72],
        "PHILIPS_OVU710023_KEY_1": [56, 75, 73],
        "PHILIPS_OVU710023_KEY_2": [56, 76, 82],
        "PHILIPS_OVU710023_KEY_3": [56, 76, 79],
        "PHILIPS_OVU710023_KEY_4": [56, 76, 80],
        "PHILIPS_OVU710023_KEY_5": [56, 76, 81],
        "PHILIPS_OVU710023_KEY_6": [56, 76, 75],
        "PHILIPS_OVU710023_KEY_7": [56, 76, 76],
        "PHILIPS_OVU710023_KEY_8": [56, 76, 77],
        "PHILIPS_OVU710023_KEY_9": [56, 76, 71],
        "PHILIPS_OVU710023_KEY_HASH": [56, 81, 76],
        "PHILIPS_OVU710023_KEY_ASTERISK": [42, 9]
    },
    PHILIPS_OVU710023_SYSTEM_CONTROL: {
        "KEY_SLEEP": [142],
        "KEY_WAKEUP": [143]
    },
    PHILIPS_OVU710023_CONSUMER_CONTROL: {
        "KEY_MUTE": [113],
        "KEY_VOLUMEDOWN": [114],
        "KEY_VOLUMEUP": [115],
        "KEY_PAUSE": [119],
        "KEY_PROPS": [130],
        "KEY_BACK": [158],
        "KEY_NEXTSONG": [163],
        "KEY_PREVIOUSSONG": [165],
        "KEY_STOPCD": [166],
        "KEY_RECORD": [167],
        "KEY_REWIND": [168],
        "KEY_PLAY": [207],
        "KEY_PROGRAM": [362],
        "KEY_FASTFORWARD": [208],
        "KEY_CHANNELUP": [402],
        "KEY_CHANNELDOWN": [403]
    }
}

ACTIONS = {
    "KEY_ESC": "Action(OSD)",
    "KEY_ENTER": "Action(Select)",
    "KEY_UP": "Action(Up)",
    "KEY_LEFT": "Action(Left)",
    "KEY_RIGHT": "Action(Right)",
    "KEY_DOWN": "Action(Down)",
    "PHILIPS_OVU710023_KEY_0": "Action(Number0)",
    "PHILIPS_OVU710023_KEY_1": "Action(Number1)",
    "PHILIPS_OVU710023_KEY_2": "Action(Number2)",
    "PHILIPS_OVU710023_KEY_3": "Action(Number3)",
    "PHILIPS_OVU710023_KEY_4": "Action(Number4)",
    "PHILIPS_OVU710023_KEY_5": "Action(Number5)",
    "PHILIPS_OVU710023_KEY_6": "Action(Number6)",
    "PHILIPS_OVU710023_KEY_7": "Action(Number7)",
    "PHILIPS_OVU710023_KEY_8": "Action(Number8)",
    "PHILIPS_OVU710023_KEY_9": "Action(Number9)",
    "PHILIPS_OVU710023_KEY_HASH": "Action(ContextMenu)",
    "PHILIPS_OVU710023_KEY_ASTERISK": "Action(Menu)",
    "KEY_SLEEP": "ActivateWindow(ShutdownMenu)",
    "KEY_WAKEUP": "Action(togglefullscreen)",
    "KEY_MUTE": "Action(Mute)",
    "KEY_VOLUMEDOWN": "Action(VolumeDown)",
    "KEY_VOLUMEUP": "Action(VolumeUp)",
    "KEY_BACK": "Action(Back)",
    "KEY_PAUSE": "Action(Pause)",
    "KEY_PROPS": "Action(Info)",
    "KEY_NEXTSONG": "Action(SkipNext)",
    "KEY_PREVIOUSSONG": "Action(SkipPrevious)",
    "KEY_STOPCD": "Action(Stop)",
    "KEY_RECORD": "Action(Record)",
    "KEY_REWIND": "Action(Rewind)",
    "KEY_PLAY": "Action(Play)",
    "KEY_PROGRAM": "Action(Playlist)",
    "KEY_FASTFORWARD": "Action(FastForward)",
    "KEY_CHANNELUP": "Action(ChannelUp)",
    "KEY_CHANNELDOWN": "Action(ChannelDown)"
}


class Listener(xbmc.Monitor):

    _listeners = None
    _last_action_ts = 0

    def __init__(self):

        xbmc.Monitor.__init__(self)

        self._listeners = []

    def _evtest_find_devices(self):

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

    def start(self):

        def _has_listener(_i):
            for _l in self._listeners:
                if _l["name"] == _i:
                    return True
            return False

        _input_devices = self._evtest_find_devices()
        for _input in INPUTS:
            if _input in _input_devices and not _has_listener(_input):
                self._start(_input, _input_devices[_input])
                time.sleep(0.2)

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

        def _match_event(sequence):

            if sequence == []:
                return None

            for known_inputs in INPUTS:
                for known_event in INPUTS[known_inputs]:
                    if INPUTS[known_inputs][known_event] == sequence:
                        return known_event

            return None

        found_event = _match_event(sequence)
        if found_event:
            xbmc.log("[Philips remote] event found: %s" %
                     found_event, xbmc.LOGDEBUG)
            if self._is_display_on():
                xbmc.executebuiltin(ACTIONS[found_event])
            return True

        return False

    def _is_display_on(self):

        current_time = time.time()
        if self._last_action_ts + 299 > current_time:
            return True

        ps = subprocess.Popen(
            ["xset", "-q"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = ps.communicate()
        self._last_action_ts = current_time
        if not re.search("Monitor is On", stdout):
            xbmc.log("[Philips remote] turn monitor on", xbmc.LOGNOTICE)
            subprocess.call(["xset", "dpms", "force", "on"])
            return False
        else:
            return True

    def clean(self):

        for l in self._listeners:
            l["subprocess"].kill()


if __name__ == "__main__":
    xbmc.log("[Philips remote] Service started", xbmc.LOGNOTICE)
    listener = Listener()
    listener.start()

    while not listener.abortRequested():
        if listener.waitForAbort(10):
            pass

    xbmc.log("[Philips remote] stopping service", xbmc.LOGNOTICE)
    listener.clean()
    xbmc.log("[Philips remote] Service stopped.", xbmc.LOGNOTICE)
