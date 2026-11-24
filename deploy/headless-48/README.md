# Festimix HP headless 48/48 — rehearsal setup

This is an opt-in, user-systemd autostart package on top of the source commit `5a5729c3` saved as `stable/usable-48x48-2026-11-24`. The running HP binary is the actual reference and is copied unchanged before anything is enabled. The installer **does not start or stop audio**, does not edit Netplan/Wi-Fi, and does not enable Linux graphical login.

## Install once while current system still runs

```bash
cd ~/projects/tascam_us1641_linux
git fetch origin
git switch feature/headless-boot-48
git pull --ff-only origin feature/headless-boot-48
bash deploy/headless-48/install.sh
loginctl show-user "$(id -un)" -p Linger
ls -l ~/.local/share/festimix-48/tascamd-known-good
sha256sum -c ~/.local/share/festimix-48/tascamd.sha256
```

The first copy of `tascamd-known-good` is never overwritten by rerunning the installer. It is important that `build/tascamd` is the previously heard **working 48/48 binary** before running it.

## Controlled activation (once)

In the existing manual AUDIO terminal Ctrl+C stops the old driver. Stop manual DSP and Node processes in their own terminal(s) with Ctrl+C or controlled SIGTERM; there must be no duplicate Tascam USB daemon, DSP, or Node. Then in a third CONTROL SSH terminal:

```bash
systemctl --user start festimix-quantum.service
systemctl --user start festimix-tascam.service
systemctl --user start festimix-dsp.service
systemctl --user start festimix-route.service
systemctl --user start festimix-web.service
systemctl --user --no-pager status festimix-{quantum,tascam,dsp,route,web}.service
```

Check `pgrep -af '[t]ascamd-known-good|[f]estimix_linux_host|[n]ode server.js'` for *exactly one* of each, and `pw-top` for QUANT=48. Keep mixer outputs low at first start. Open `http://192.168.0.237:3000` **only if this Wi-Fi DHCP address is still valid**.

Service logs:

```bash
journalctl --user -u festimix-tascam -u festimix-dsp -u festimix-route -u festimix-web -b --no-pager -n 100
```

With user linger enabled, systemd starts the user services on boot before login and restarts crashed processes. The route service checks all links every 5s to recover after graph restarts. If `pipewire` itself fails or changes graph generation, some manual recovery may still be necessary; test an actual reboot before relying on it on stage. This is a rehearsal prototype, not fail-safe life-safety infrastructure.

## Reboot acceptance test

```bash
sudo reboot
```

Then reconnect over SSH **without logging in locally**, and verify all statuses / PipeWire. Reboot may change DHCP address unless fixed in router. Ensure wired network is not the only means of access before unplugging.

## Rehearsal Wi-Fi warning

The current config joins **TANET-2** (a network from the present site). At rehearsal without TANET-2, the HP will not join Wi-Fi, even if all local audio services start. iPad control requires a common network. Bring a portable router/access point, connect HP and iPad to its SSID, or deliberately preconfigure the actual rehearsal Wi-Fi. Prefer a dedicated offline LAN; internet connectivity is not required. Don't cut off SSH until tested in the new network. To run without any Wi-Fi in rehearsal, local audio processing can continue, but iPad remote control will be unavailable.

## Configuration limitations

- Autostart ≠ preset persistence: the Linux DSP's in-memory control journal does **not** automatically restore channel processing settings after reboot. Load the intended scene manually and independently validate all faders, AUX, mutes and outputs. Do not promise auto restored mixing settings.
- This deploys the currently known-good *Tascam* executable, not a frozen DSP/Node build; if DSP binaries or JS change in the directories, those changes affect the next restart.
- If the Tascam binary file under `~/.local/share/festimix-48` does not match the known-good SHA256, do not start it.
- Service unit configs are in `~/.config/systemd/user`; disable autostart with:
```bash
systemctl --user disable --now festimix-web.service festimix-route.service festimix-dsp.service festimix-tascam.service festimix-quantum.service
```
Stopping the driver will of course stop audio.
