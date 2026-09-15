#!/usr/bin/env python3
"""Apply WSL/Windows-Webots patches to webots_ros2_driver/utils.py.

Run with root privileges:
    sudo python3 scripts/patch_webots_ros2_driver.py

The script is idempotent and patches:
  1. is_wsl(): keep native Linux Webots mode working, while allowing the
     Windows-Webots WSL mode.
  2. get_wsl_ip_address(): prefer the WSL default-route gateway (the Windows
     host address) instead of the /etc/resolv.conf DNS proxy.
"""
from pathlib import Path
import sys

UTILS = Path("/opt/ros/humble/local/lib/python3.10/dist-packages/webots_ros2_driver/utils.py")
NL = chr(10)

if not UTILS.exists():
    print("utils.py not found:", UTILS)
    sys.exit(1)

s = UTILS.read_text()

# 1) is_wsl()
old_is_wsl = (
    "def is_wsl():" + NL
    + "    return 'microsoft-standard' in uname().release" + NL
)
new_is_wsl = (
    "def is_wsl():" + NL
    + "    webots_home = os.environ.get('WEBOTS_HOME', '')" + NL
    + "    if webots_home.startswith('/') and os.path.isfile(os.path.join(webots_home, 'webots')):" + NL
    + "        return False" + NL
    + "    return 'microsoft-standard' in uname().release" + NL
)
if old_is_wsl in s:
    s = s.replace(old_is_wsl, new_is_wsl, 1)
    print("patched is_wsl()")
elif "webots_home = os.environ.get('WEBOTS_HOME', '')" in s:
    print("is_wsl() already patched")
else:
    print("WARNING: is_wsl() pattern not found")

# 2) get_wsl_ip_address()
start = s.find("def get_wsl_ip_address():")
end = s.find("def has_shared_folder():")
if start != -1 and end != -1 and start < end:
    new_func = (
        "def get_wsl_ip_address():" + NL
        + "    # Prefer the default-route gateway: in WSL2 NAT mode this is the" + NL
        + "    # Windows host address that Webots listens on." + NL
        + "    try:" + NL
        + "        output = subprocess.run(" + NL
        + "            ['ip', 'route']," + NL
        + "            check=True," + NL
        + "            stdout=subprocess.PIPE," + NL
        + "            universal_newlines=True," + NL
        + "        )" + NL
        + "        for line in output.stdout.split(chr(10)):" + NL
        + "            fields = line.split()" + NL
        + "            if fields and fields[0] == 'default':" + NL
        + "                return fields[2]" + NL
        + "    except Exception:" + NL
        + "        pass" + NL
        + NL
        + "    try:" + NL
        + "        file = open('/etc/resolv.conf', 'r')" + NL
        + "    except IOError:" + NL
        + "        return '127.0.0.1'" + NL
        + "    try:" + NL
        + "        for line in file:" + NL
        + "            if len(line) == 0 or line[0] == '#' or line[0] == ';':" + NL
        + "                continue" + NL
        + "            tokens = line.split()" + NL
        + "            if len(tokens) == 0:" + NL
        + "                continue" + NL
        + "            if tokens[0] == 'nameserver':" + NL
        + "                file.close()" + NL
        + "                if len(tokens[1]) == 0:" + NL
        + "                    return '127.0.0.1'" + NL
        + "                return tokens[1]" + NL
        + "    finally:" + NL
        + "        file.close()" + NL
        + NL + NL
    )
    s = s[:start] + new_func + s[end:]
    print("patched get_wsl_ip_address()")
else:
    print("WARNING: get_wsl_ip_address() boundaries not found")

UTILS.write_text(s)
print("done:", UTILS)
