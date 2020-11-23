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

KEY_LEFTSHIFT = 42
KEY_LEFTALT = 56

INPUTS = {
    PHILIPS_OVU710023_KEYBOARD: {
        "KEY_ESC": [1],
        "KEY_ENTER": [28],
        "KEY_UP": [103],
        "KEY_LEFT": [105],
        "KEY_RIGHT": [106],
        "KEY_DOWN": [108],
        "PHILIPS_OVU710023_KEY_0": [75, 72],
        "PHILIPS_OVU710023_KEY_1": [75, 73],
        "PHILIPS_OVU710023_KEY_2": [76, 82],
        "PHILIPS_OVU710023_KEY_3": [76, 79],
        "PHILIPS_OVU710023_KEY_4": [76, 80],
        "PHILIPS_OVU710023_KEY_5": [76, 81],
        "PHILIPS_OVU710023_KEY_6": [76, 75],
        "PHILIPS_OVU710023_KEY_7": [76, 76],
        "PHILIPS_OVU710023_KEY_8": [76, 77],
        "PHILIPS_OVU710023_KEY_9": [76, 71],
        "PHILIPS_OVU710023_KEY_HASH": [81, 76],
        "PHILIPS_OVU710023_KEY_ASTERISK": [9]
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

# missing keys are:
# - Windows MCE
# - Teletext: red, green, yellow, blue, ?

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

    _philips_input_devices = None
    _req_id = 0
    _listeners = None
    _last_action_ts = 0

    def __init__(self):

        xbmc.Monitor.__init__(self)

        self._philips_input_devices = self._evtest_find_devices()
        self._listeners = []

    def start(self):

        for _input in INPUTS:
            self._start(_input)

    def terminate(self):

        i = 0
        for l in self._listeners:
            i += 1
            xbmc.log("[Philips remote] terminating listener %i of %i ..." %
                     (i, len(self._listeners)), xbmc.LOGNOTICE)
            l.kill()
            xbmc.log("[Philips remote] listener %i terminated." %
                     (i), xbmc.LOGNOTICE)

    def kill(self):

        ps = subprocess.Popen(["ps", "-eo", "pid,args"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = ps.communicate()
        for line in stdout.splitlines():
            pid, cmdline = line.split(" ", 1)
            if cmdline.startswith("evtest"):
                xbmc.log(
                    "[Philips remote] still running process with PID %i found" % pid, xbmc.LOGERROR)

    def _evtest_find_devices(self):

        p1 = subprocess.Popen(["echo", "-e", "\n"], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(["evtest"], stdin=p1.stdout,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.stdout.close()
        out, err = p2.communicate()

        xbmc.log(err, xbmc.LOGNOTICE)

        devices = {}
        for line in err.decode("utf-8").split("\n"):
            m = re.search(r"(/dev/input/event[0-9]+).*(PHILIPS OVU.+)", line)
            if m:
                devices[m.group(2)] = m.group(1)
                xbmc.log("[Philips remote] found %s at %s" %
                         (m.group(2), m.group(1)), xbmc.LOGNOTICE)

        return devices

    def _start(self, input_dev_name):

        if input_dev_name in self._philips_input_devices:
            path = self._philips_input_devices[input_dev_name]
            l = threading.Thread(target=self._listen, args=(path,))
            l.daemon = True
            l.start()
            xbmc.log("[Philips remote] started listener for %s at %s" %
                     (input_dev_name, path), xbmc.LOGNOTICE)
            return l
        else:
            xbmc.log("[Philips remote] %s device not found and not started" %
                     input_dev_name, xbmc.LOGERROR)
            return None

    def _listen(self, path):

        def _match_event(known_events, sequence):

            for known_event in known_events:
                if known_events[known_event] == sequence:
                    return known_event

            return None

        def _parse_event(line):

            xbmc.log(line, xbmc.LOGDEBUG)

            m = re.search(
                r"type 1 \(EV_KEY\), code ([0-9]+) \(([^\)]+)\), value ([012]+)", line)
            return {
                "state": int(m.group(3)),
                "key_state": ("UP", "DOWN", "HOLD")[int(m.group(3))],
                "scan_code": int(m.group(1)),
                "key_code": m.group(2)
            } if m else None

        proc = subprocess.Popen(
            ["evtest", "--grab", path], stdout=subprocess.PIPE)
        self._listeners.append(proc)

        sequence = None
        for line in iter(proc.stdout.readline, ""):

            event = _parse_event(line)

            if self.abortRequested():
                break

            if event:
                xbmc.log("[Philips remote] incoming raw event: %s, %s" %
                         (event["key_state"], event["key_code"]), xbmc.LOGDEBUG)

                if event["state"] == KEY_STATE_DOWN and event["scan_code"] in [KEY_LEFTALT, KEY_LEFTSHIFT]:
                    sequence = []
                elif event["state"] == KEY_STATE_DOWN and sequence is not None:
                    sequence.append(event["scan_code"])
                elif event["state"] == KEY_STATE_UP and event["scan_code"] in [KEY_LEFTALT, KEY_LEFTSHIFT]:
                    found_event = _match_event(
                        INPUTS[PHILIPS_OVU710023_KEYBOARD], sequence)
                    if found_event:
                        xbmc.log("[Philips remote] complex key event detected: %s" %
                                 found_event, xbmc.LOGDEBUG)
                        self._perform_action_by_keycode(found_event)
                    sequence = None
                elif event["state"] in [KEY_STATE_DOWN, KEY_STATE_HOLD] and sequence is None:
                    xbmc.log("[Philips remote] simple key event detected: %s" %
                             event["key_code"], xbmc.LOGDEBUG)
                    self._perform_action_by_keycode(event["key_code"])

    def _perform_action_by_keycode(self, key_code):

        if self._is_display_on():
            xbmc.executebuiltin(ACTIONS[key_code])

    def _is_display_on(self):

        current_time = time.time()
        if self._last_action_ts + 299 > current_time:
            return True

        ps = subprocess.Popen(
            ["xset", "-q"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout = ps.communicate()
        if re.search(r"Monitor is in Suspend", stdout):
            xbmc.log("[Philips remote] turn monitor on", xbmc.LOGNOTICE)
            subprocess.call(["xset", "dpms", "force", "on"])
            self._last_action_ts = current_time
            return False
        else:
            return True


if __name__ == "__main__":
    xbmc.log("[Philips remote] Service started", xbmc.LOGNOTICE)
    listener = Listener()
    listener.start()

    while not listener.abortRequested():
        if listener.waitForAbort(10):
            break

    xbmc.log("[Philips remote] stopping service", xbmc.LOGNOTICE)
    listener.terminate()
    time.sleep(1)
    listener.kill()
    xbmc.log("[Philips remote] Service stopped.", xbmc.LOGNOTICE)
