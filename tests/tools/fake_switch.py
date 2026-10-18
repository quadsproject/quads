#!/usr/bin/env python3
"""Fake switch console for SwitchCLI tests.

Emulates enough of a Junos/Arista session over a PTY to exercise the
real pexpect runner: an operational '>' prompt, a config-mode '#'
prompt after edit/configure terminal, commit/copy markers, a VLAN
show reply, and EOS-style '%' error output.
"""

import os
import sys


def read_line():
    buf = b""
    while True:
        chunk = os.read(0, 1)
        if not chunk:
            return None
        buf += chunk
        if chunk == b"\n":
            return buf.decode()
    return None


def emit(text):
    os.write(1, text.encode())


def main():
    # --enable: start in config/enable mode ('#'), like an arista
    # scaleadmin session that drops straight into enable.
    mode = "cfg" if "--enable" in sys.argv else "op"
    prompt = {"op": "user@lab> ", "cfg": "user@lab# "}
    if "--enable" in sys.argv:
        # Arista scaleadmin drops into enable mode: '#' in both modes.
        prompt = {"op": "user@lab# ", "cfg": "user@lab# "}
    emit(prompt[mode])
    while True:
        line = read_line()
        if line is None:
            return
        line = line.strip()
        if line == "edit":
            mode = "cfg"
        elif line == "configure terminal":
            mode = "cfg"
        elif line == "exit":
            if mode == "cfg":
                mode = "op"
        elif line == "rollback":
            pass
        elif line.startswith(("delete ", "set ")):
            pass
        elif line.startswith("show configuration vlans"):
            emit("set vlans vlan1110 interface et-0/0/0:0.0\n")
        elif line.startswith("show running-config interfaces"):
            emit("switchport access vlan 1110\nswitchport mode dot1q-tunnel\n")
        elif line == "commit":
            emit("commit complete\n")
        elif line in ("write memory", "copy running-config startup-config"):
            if line == "copy running-config startup-config" and "--deny-copy" in sys.argv:
                emit("% Authorization denied for command 'copy running-config startup-config'\n")
            else:
                emit("Copy completed successfully.\n")
        elif line.startswith("interface "):
            pass
        elif line.startswith("default interface"):
            emit("% Authorization denied for command 'default interface Ethernet10/2'\n")
        elif line == "terminal length 0":
            pass
        elif line.startswith("speed forced") and "--confirm" in sys.argv:
            # EOS group-wide speed change: lists the port group and asks.
            emit("\n   Ethernet7/2\n   Ethernet7/3\n\nDo you wish to proceed with this command? [y/N]")
            ans = read_line()
            if ans is None:
                return
            if ans.strip().lower() != "y":
                emit("Operation cancelled.\n")
            emit(prompt[mode])
            continue
        elif line.startswith(
            (
                "no switchport",
                "switchport mode",
                "switchport access",
                "switchport trunk",
                "speed auto",
                "speed forced",
                "error-correction",
            )
        ):
            pass
        else:
            emit(f"% Invalid input: {line}\n")
        emit(prompt[mode])


if __name__ == "__main__":
    main()
