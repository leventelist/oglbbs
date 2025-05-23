# Python Packet BBS

A simple AGWPE-compatible BBS server using [pyham_pe](https://github.com/mfncooper/pyham_pe) and SQLite. This was inspired by the APRS-BBS by [TCC](https://github.com/TheCommsChannel/TC2-APRS-BBS). I really like the concept, but I wanted to be connection oriented to use the capabilities of AX.25/IL2P.

The development is on Debian Linux. It should work on other platforms, but your mileage may vary.

I filed a feature request for a connection oriented BBS, but in the meanwhile, I wrote my own. :-)

## Features

* AGWPE support
* Broadcast messages
* Private messages
* SQLite backend
* SSH interface


## Install

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip3 install -r requirements.txt
```

## Creating pyz
```bash
pip3 install shiv
shiv -o oglbbs.pyz -e oglbbs.oglbbs:main .
```
This will create a portable pyz file that you can copy wherever you want.

## Configuration

Edit `oglbbs.conf`.

## Running

```bash
oglbbs.pyz -c oglbbs.conf
```

## TODO

* Displaying unread message counter for connecting users.
* Displaying emergency messages for newly connected users.
* File transfer
* Testing
* Testing
* Testing

73's de HA5OGL
