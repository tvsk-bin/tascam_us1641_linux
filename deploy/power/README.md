# Festimix POWER (iPad shutdown, no SSH on each use)

This adds a **separate** built-in-Python web page at port **3001**, leaving audio services, the stable 48/48 driver and current Festimix UI untouched. Not integrated into Festimix main web UI yet. Intended for **trusted private LANs only**: plain HTTP means the access code can be observed by another user on a compromised Wi-Fi.

## Install on HP once over SSH

```bash
cd ~/projects/tascam_us1641_linux
git fetch origin
git switch feature/ipad-poweroff
git pull --ff-only origin feature/ipad-poweroff
bash deploy/power/install.sh
systemctl --user status festimix-power --no-pager
```

Installer asks for sudo for one narrowly scoped passwordless shutdown privilege (exact command `/usr/bin/systemctl poweroff`), validates it with `visudo`, generates a 192-bit random access code and shows it **once**. Record it privately. Requires existing user linger from headless-48 setup for boot autostart.

Navigate on iPad to `http://192.168.0.237:3001/` *only if 192.168.0.237 is still the HP's assigned Wi-Fi IP*. Enter access code, tap **SHUTDOWN**, wait 5 seconds, then tap **SURE**. Server independently enforces the 5-second wait and 45-second expiry. A wrong code cannot power off. HTTP response comes before the delayed system shutdown; connection loss is expected.

If the poweroff fails, inspect `journalctl --user -u festimix-power -n 50 --no-pager`.

### Warning
- **No remote power-on**: once shut down, press HP physical power switch to start it again.
- Shutdown stops audio immediately. Do not use during playback/recording.
- Any person who knows the access code on the LAN can request shutdown. Do not expose port 3001 to the Internet, router port forwarding, or public Wi-Fi. Prefer private router.
- No UPS/battery guarantee; a failed AC supply still interrupts audio.
- If access code is disclosed, change file `~/.config/festimix-power/access-key` to a new random 32+ character code, then restart service.
- All data/state is only persisted to the extent Festimix already does so; there is not yet guaranteed scene recall at boot.

### Disable
```bash
systemctl --user disable --now festimix-power.service
sudo rm /etc/sudoers.d/festimix-poweroff
```
