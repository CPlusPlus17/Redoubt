#!/usr/bin/env python3
"""Ask the guest to shut down gracefully through QMP."""
import json
import os
import socket
import sys
from pathlib import Path

state = Path(os.environ.get('REDOUBT_VM_STATE', Path.home() / '.local/share/redoubt-ci-vm'))
with socket.socket(socket.AF_UNIX) as client:
    client.settimeout(10)
    try:
        client.connect(str(state / 'qmp.sock'))
    except (FileNotFoundError, ConnectionRefusedError):
        sys.exit(0)
    stream = client.makefile('rwb')
    json.loads(stream.readline())
    for command in ('qmp_capabilities', 'system_powerdown'):
        stream.write((json.dumps({'execute': command}) + '\r\n').encode())
        stream.flush()
        while True:
            result = json.loads(stream.readline())
            if 'error' in result:
                raise RuntimeError(result['error'])
            if 'return' in result:
                break
