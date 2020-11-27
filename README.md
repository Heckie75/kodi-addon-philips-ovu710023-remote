# kodi-addon-philips-ovu710023-remote
Kodi addon in order to use ZOTAC Remote Control Kit (Philips OVU710023)

This is a Kodi addon which allows usage of the Philips OVU710023 remote control. It is especially known as the Zotac Remote Control Kit, see [offer by Mindfactory](https://www.mindfactory.de/product_info.php/Zotac-Remote-Control-Kit-USB-IR-receiver_956848.html)

This remote control does not work very well out of the box in Linux. It differs from other IR receivers because it emulates several input devices, i.e. a keyboard with media controls and power buttons. Some buttons work out of the box since they are simply mapped to standard keys. But there are several buttons that don't work. These are the numeric keys, asterisk key and hash key. Although the media control buttons, like _play_ or _pause_, work from scratch from operation system's point of view, I also mapped these to the commands that are expected in Kodi so that no additionally setup is required.

However, there are limitations. First of all, this addon works only for Linux. It does not work on Microsoft Windows, Android, LibreElec and others. Further, it utilizes several command line tools which must be available and executable.

## Preconditions

### Check hardware

This addon supports _Philips (or NXP) OVU710023_

Plugin the receiver and perform the following:
```
$ lsusb
...
Bus 001 Device 015: ID 0471:2168 Philips (or NXP) OVU710023
...
```

If you find a device with hardware ID ```0471:2168``` called _Philips (or NXP) OVU710023_ you are fine.

As mentioned this addon only works on Linux based systems. It uses command line tools which must be checked and - in some cases - installed first. 

### evtest

This addon grabs events from input sources by utilizing ```evtest```

Make sure that ```evtest``` is installed and that you have granted permissions to read from input devices:

```
$ # check if evtest is available

$ which evtest
/usr/bin/evtest

$ # if not install it

$ # check if current user has granted access to input devices
$ # $ ls -l /dev/input/event* | head -n2
crw-rw---- 1 root input 13, 64 Nov 17 05:46 /dev/input/event0
crw-rw---- 1 root input 13, 65 Nov 17 05:46 /dev/input/event1

$ # It is required that current user is in group 'input'
$ groups
adm dialout fax cdrom video plugdev lpadmin lxd sambashare 

$ # If current user is not in group 'input' as seen in this case then add user to this group
$ sudo usermod -a -G input <your username>
```

After you have checked ```evtest``` and permissions the output of ```evtest``` should look like this:

```
$ 
/dev/input/event5:      Video Bus
# ...
/dev/input/event17:     PHILIPS OVU710023 Keyboard
/dev/input/event18:     PHILIPS OVU710023 System Control
/dev/input/event19:     PHILIPS OVU710023 Consumer Control
/dev/input/event20:     PHILIPS OVU710023 Mouse
...
Select the device event number [0-23]: 
```

**Note**

You may ask why I haven't used the Python module ```evtest```?! The reason is that Kodi 18.x still runs Python 2.x which comes with a small footprint of extra modules.

### xset

Suprisingly this addon requires ```xset``` as well. This is because your monitor maybe turns into standby / suspend after some time. In this case you expect that the first key press switches your monitor on. 

In order to do this ```xset``` is required. It asked the current state of the monitor and turns it on if required. 

Check if xset is available like this:
```
$ which xset
/usr/bin/xset

$ ... and if you can use this comment like this
$ xset dpms force suspend && sleep 5 && xset dpms force on
```

### Install addon

You can download the addon as archive [script.service.philips-ovu710023-remote.zip](/script.service.philips-ovu710023-remote.zip)

## Troubleshooting

### Install addon, plugin receiver and start Kodi

After you have installed this addon you MUST restart Kodi since it starts as a service when Kodi starts.

I have  optimized this addon, so that it detects if you plugin the device while Kodi is running. 

After you have plugged in and started Kodi you can check Kodi's logs if everything works fine. It should look like this:
```
2020-11-23 17:33:30.657 T:140689580984064  NOTICE: [Philips remote] Service started
2020-11-23 17:33:31.772 T:140689580984064  NOTICE: [Philips remote] found PHILIPS OVU710023 Keyboard at /dev/input/event17
2020-11-23 17:33:31.772 T:140689580984064  NOTICE: [Philips remote] found PHILIPS OVU710023 System Control at /dev/input/event18
2020-11-23 17:33:31.772 T:140689580984064  NOTICE: [Philips remote] found PHILIPS OVU710023 Consumer Control at /dev/input/event19
2020-11-23 17:33:31.772 T:140689580984064  NOTICE: [Philips remote] found PHILIPS OVU710023 Mouse at /dev/input/event20
2020-11-23 17:33:31.776 T:140689580984064  NOTICE: [Philips remote] started listener for PHILIPS OVU710023 System Control at /dev/input/event18
2020-11-23 17:33:31.794 T:140689580984064  NOTICE: [Philips remote] started listener for PHILIPS OVU710023 Keyboard at /dev/input/event17
2020-11-23 17:33:31.794 T:140689580984064  NOTICE: [Philips remote] started listener for PHILIPS OVU710023 Consumer Control at /dev/input/event19
```

### Hanging processes after shutdown

As mentioned the addon starts a service. This service starts three sub-processes (daemons) that listen the input devices.

I spent a lot of time in order to end sub-processes when Kodi shuts down. But I have seen that this sometimes don't work as expected and processes are hanging. 

You can see these processes by grepping like this:
```
$ ps -ef | grep evtest 
user    289686  289625  0 18:18 ?        00:00:00 evtest --grab /dev/input/event17
user    289687  289625  1 18:18 ?        00:00:00 evtest --grab /dev/input/event18
user    289688  289625  0 18:18 ?        00:00:00 evtest --grab /dev/input/event19
```

And if required you can kill these proceses like this:
```
$ pkill evtest
```

## Limitations

I have decided how to map the remote buttons. If you take a look at source code you should be able to map buttons in a different way.

Nevertheless, there are 6 buttons that don't at all. I have tested this by using Linux Kernel 5.4.

The following buttons don't work:
* Teletext buttons: red, green, yellow, blue and ?-button
* Windows MCE button: the green one with Windows logo inside