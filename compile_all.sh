#! /bin/sh

./bootstrap
./configure --enable-ftdi --enable-presto_libftdi --enable-openjtag_ftdi --enable-shared --disable-internal-jimtcl --enable-dummy
make -j4
