Wifi Usb dongle:
https://www.amazon.com/dp/B00UJEOTXQ?ref=ppx_yo2ov_dt_b_fed_asin_title


Install the drivers
```
sudo apt update
sudo apt install -y git dkms build-essential linux-headers-$(uname -r)
git clone https://github.com/Mange/rtl8192eu-linux-driver.git
cd rtl8192eu-linux-driver
```


```
vim Makefile 
```
set all CONFIG_PLATFORM_* to `n`
ARM will be the default

```
sudo apt install -y linux-headers-4.19.94-ti-r42
sudo apt install -y linux-headers-4.19.94-ti-r42
ls /lib/modules/$(uname -r)/build
sudo dkms install rtl8192eu/1.0

cd ~
git clone https://github.com/kimocoder/rtl8192eu
cd rtl8192eu


ip link
```



✅ 1️⃣ Make Sure ConnMan Is Running
```
sudo systemctl enable connman
sudo systemctl start connman
```

Verify:
```
systemctl status connman
```

✅ 2️⃣ Connect Once (ConnMan Saves It)

ConnMan remembers networks after the first successful connect.
```
connmanctl
```

Inside the prompt:
```
enable wifi
scan wifi
services
```

You’ll see something like:
```
*AO MyWifiName        wifi_001122334455_4d79576946694e616d65_managed_psk
```

Now connect:
```
agent on
connect wifi_001122334455_4d79576946694e616d65_managed_psk
```

Enter your WiFi password.

Exit:
```
quit
```
✅ 3️⃣ Set Wi-Fi Higher Priority Than Ethernet

ConnMan prefers ethernet by default. Let’s flip that so WiFi connects even if eth0 is plugged in.

Edit the config:
```
sudo vim /etc/connman/main.conf
```

Set:
```
[General]
PreferredTechnologies = wifi,ethernet
SingleConnectedTechnology = false
```

Save & restart:
```
sudo systemctl restart connman
```
✅ 4️⃣ Lock WiFi to Always Auto-Connect

Find your saved service:
```
ls /var/lib/connman/
```

You’ll see something like:
```
wifi_001122334455_4d79576946694e616d65_managed_psk
```

Edit its settings:
```
sudo vim /var/lib/connman/wifi_*/settings
```

Make sure this exists:
```
AutoConnect=true
```

If it’s missing, add it.

Restart ConnMan:
```
sudo systemctl restart connman
```
✅ 5️⃣ Test Reboot Auto-Connect
```
sudo reboot
```

After reboot:
```
ip a
```

You should see:
```
wlan0 UP
inet 192.168.x.x
```

Or:
```
connmanctl state
```

Should say:
```
State = online
```
