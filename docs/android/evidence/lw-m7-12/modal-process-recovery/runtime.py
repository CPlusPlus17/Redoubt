#!/usr/bin/env python3
"""Run the frozen runtime functions with the explicitly bound modal retry adapter."""
import common as c

c.inherited_inputs()
implementation = c.private_module('modal_private_frozen_runtime', c.FROZEN / 'runtime.py', common=c)


def __getattr__(name):
    return getattr(implementation, name)


if __name__ == '__main__':
    raise SystemExit(implementation.main())
