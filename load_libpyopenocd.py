from ctypes import *

liboocd = cdll.LoadLibrary("/home/user/openocd/openocd/src/.libs/libpyopenocd.so.0.0.0")

cmd_ctx = liboocd.create_command_handler(None)

argv = (c_char_p * 1)(
        b'script ./tcl/interface/dummy.cfg',
)
r = liboocd.openocd_init(cmd_ctx, len(argv), argv)

liboocd.openocd_deinit(cmd_ctx)
