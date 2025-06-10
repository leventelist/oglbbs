# Python Packet BBS

A simple AGWPE-compatible BBS server using [pyham_pe](https://github.com/mfncooper/pyham_pe) and SQLite. This was inspired by the APRS-BBS by [TCC](https://github.com/TheCommsChannel/TC2-APRS-BBS). I really like the concept, but I wanted to be connection oriented to use the capabilities of AX.25/IL2P.

The development is on Debian Linux. It should work on other platforms, but your mileage may vary.

I filed a feature request for a connection oriented BBS, but in the meanwhile, I wrote my own. :-)


## Features

* AGWPE support
* Broadcast messages
* Private messages
* Chat with connected users
* SQLite backend
* SSH interface


## Install

### Prerequisites

You need `python` 3.10 or later with `venv`. On many systems, `python` is preinstalled.

On Debian based systems, you might need to install the venv module like this:

```bash
sudo apt install python3-venv
```

### Get oglbbs

git clone https://github.com/leventelist/oglbbs.git

### Get dependecies


```bash
cd oglbbs
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip3 install -r requirements.txt
```


## Configuration

### RSA key

To enable the SSH interface, you have to have an RSA key. If you install it to
a Linux system, you may (and encouraged to) use the key of your system. On
Debian, it is located at `/etc/ssh/ssh_host_rsa_key`.

If you want to generate an SSH key, you can do that by

```bash
ssh-keygen -t ed25519 -N "" -f oglbbs_ed25519 -q
```

Or if you want to stick to the good old, but now legacy RSA key for some reason, use:

```bash
ssh-keygen -t rsa -b 4096 -N "" -f oglbbs_rsa -q
```

Add the generated private key file name to your config file. See below.

### Configuration file

Edit `oglbbs.conf` according to your key and other settings. You must edit the callsign of the BBS.
The program will look for the config file in the directory it was started. It is however very encouraged
to use the `-c` command line option to specify explicitly the location of the configuration file. See below.


## Running

You can start the application like this:

```bash
python3 -m oglbbs.main -c ./oglbbs.conf
```


## Creating pyz (optional)

```bash
shiv -o oglbbs.pyz -e oglbbs.oglbbs:main .
```
This will create a portable pyz file that you can copy wherever you want.

You can run the pyz like this

```bash
oglbbs.pyz -c ./oglbbs.conf
```


## Accessing the BBS on its radio interface

You can use any terminal program. Here is a list of some.

* [agwpe-tools](https://github.com/jmkristian/agwpe-tools) If you are really a command
line warrior.
* [paracon](https://github.com/mfncooper/paracon) This one uses the same
packet engin as this BBS.
* [linpac](https://sourceforge.net/projects/linpac/) I think it uses the
AX.25 implemetation of the kernel. This might not work if your BBS is
running in IL2P, which is encouraged.


## SSH port

The SSH port is created to be able to login to the BBS from a local TCP/IP network. There is a soft authentication. Be sure to use your callsign as username, and a password. This password will be saved and used for further logins.

Please use a valid callsign. This is validated, and if fails, it will not log you in.

```bash
ssh -p8002 ha5ogl@radio
```

The example above shows how I usually log in to the BBS from the local network. `ha5ogl` is my callsign, and `radio` is the hostname of the computer running the BBS. -p specifies the port.

## Usage

Once set up, the BBS supports the following commands:

### HELP

Syntax: `HELP`

Prints a summary of the available commands.

### INFO

Syntax: `INFO`

Prints a general information.

### MSG

Syntax: `MSG message`

Post a public message that can everybody read.

### LIST

Syntax: `LIST`

Show recent public messages.

### SEND

Syntax: `SEND CALL message`

Sends a message to callsign CALL. The mesage will be stored in the database. The message is terminated by a newline character. In practice, when you press enter. Multiline messages are not yet supported.

### READ

Syntax: `READ`

Read all your private messages.

### DEL

Syntax: `DEL ID`

Delete message with ID `ID`.

### VER

Syntax: `VER`

Prints version information

### CHAT

Syntax: `CHAT CALL`

Initiates a real time chat with a user is currently connected. (See the `WHO` command). Chat request can be accepted by the `ACCEPT` command, when prompted. To end a chat, use the `_EOF_` in a single line.

### WHO

Syntax: `WHO`

Prints currently connected users.

### BYE

Syntax: `BYE`

Disconnect from the BBS


## TODO

* Displaying emergency messages for newly connected users
* Multi line messages.
* Synchronize message requests.
* Send Goodby message when the BBS is shut down
* File transfer
* Baecon using UI frames.
* Scheduled houskeeping
* Standard emergency forms
* WX forcast
* Propagation forcast
* Local repeater information

73's de HA5OGL
