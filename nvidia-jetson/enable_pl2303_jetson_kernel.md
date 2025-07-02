# Enable the PL2303 USB‑to‑Serial Driver on Jetson‑Orin (Linux 5.15‑tegra)

This guide shows how to turn on **`CONFIG_USB_SERIAL_PL2303`**—either as a module (`m`) or built‑in (`y`)—for the exact kernel that ships with JetPack 6 (Jetson‑Linux 36.3, kernel 5.15‑tegra).  
The same workflow applies to any Linux kernel; just adjust paths/tool‑chains as needed.

---

## Prerequisites

```bash
sudo apt update
sudo apt install build-essential bc flex bison libncurses-dev libssl-dev
```

---

## 1 . Download & unpack the matching kernel source

```bash
# Work in any scratch directory
cd ~/work
wget https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v3.0/public_sources.tbz2
tar xf public_sources.tbz2
cd Linux_for_Tegra/source
tar xf kernel_src.tbz2        # expands to kernel/kernel-jammy-src
```

Your kernel tree is now at:

```
Linux_for_Tegra/source/kernel/kernel-jammy-src
```

---

## 2 . Seed the tree with the running config

```bash
cd kernel/kernel-jammy-src
zcat /proc/config.gz > .config
```

---

## 3 . Enable **CONFIG_USB_SERIAL_PL2303**

Choose one of the three equivalent methods:

| Method | Command | What to do inside |
|--------|---------|-------------------|
| **Edit `.config`** | `nano .config` | Add or modify the line:<br>`CONFIG_USB_SERIAL_PL2303=m` |
| **menuconfig** | `make ARCH=arm64 menuconfig` | *Device Drivers → USB support → USB Serial Converter support → Prolific PL2303 …* → select **M** or **Y** |
| **nconfig** | `make ARCH=arm64 nconfig` | Same path as *menuconfig* |

> **Module (`m`) vs Built‑in (`y`)**  
> * Use **`m`** if you want the driver loadable/unloadable at runtime (smaller kernel image).  
> * Use **`y`** only if the adapter must work during very early boot (e.g. root‑over‑serial).

---

## 4 . Build just this module (fastest)

```bash
make ARCH=arm64 modules_prepare
make -j$(nproc) ARCH=arm64 M=drivers/usb/serial   # builds pl2303.ko only

# Copy the module onto the running rootfs
sudo cp drivers/usb/serial/pl2303.ko \
        /lib/modules/$(uname -r)/kernel/drivers/usb/serial/
sudo depmod -a
```

---

## 5 . (Option) Build the whole kernel + modules

```bash
export CROSS_COMPILE=<path>/bin/aarch64-linux-gnu-
make -j$(nproc) ARCH=arm64          # Image + modules
sudo make ARCH=arm64 modules_install
sudo make ARCH=arm64 install        # copies Image, System.map, etc.
```

Then flash or copy the new `Image` to `/boot/` per NVIDIA’s kernel‑customisation instructions.

---

## 6 . Reboot & verify

```bash
sudo reboot
```

After the system comes back up, plug in a PL2303 cable and run:

```bash
dmesg | grep -i pl2303
lsmod | grep pl2303           # if built as a module
```

You should see something like:

```
usbcore: registered new interface driver pl2303
pl2303 2-2.4.4:1.0: pl2303 converter detected
```

and a new device node, e.g. `/dev/ttyUSB0`.

---

✅ **PL2303 support is now enabled on your Jetson!**
