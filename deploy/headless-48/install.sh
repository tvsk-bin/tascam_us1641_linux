#!/usr/bin/env bash
set -euo pipefail

# Non-destructive Festimix 48/48 headless setup for Ubuntu user vboxuser.
# No audio process is stopped or started by this installer.
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
home="${HOME:?}"
units_dir="$home/.config/systemd/user"
data_dir="$home/.local/share/festimix-48"
mkdir -p "$units_dir" "$data_dir"
src_bin="$repo_dir/build/tascamd"
dst_bin="$data_dir/tascamd-known-good"
if [[ ! -x "$src_bin" ]]; then
  echo "ERROR: compiled Tascam binary missing: $src_bin" >&2
  exit 1
fi
if ! "$src_bin" --help | grep -q -- '--ultra-low-latency'; then
  echo "ERROR: current binary is not the tested 48/48-capable build" >&2
  exit 1
fi
if [[ -e "$dst_bin" ]]; then
  echo "Existing known-good binary is PRESERVED: $dst_bin"
else
  install -m 0755 "$src_bin" "$dst_bin"
  echo "Saved first known-good binary: $dst_bin"
fi
if ! "$dst_bin" --help | grep -q -- '--ultra-low-latency'; then
  echo "ERROR: saved binary does not support ultra-low-latency" >&2
  exit 1
fi
sha256sum "$dst_bin" | tee "$data_dir/tascamd.sha256"
"$dst_bin" --version | tee "$data_dir/tascamd-version.txt"
dsp_src="$home/projects/festimix-audio-bench/build-linux/festimix_linux_host"
dsp_dst="$data_dir/festimix_linux_host-known-good"
if [[ ! -x "$dsp_src" ]]; then
  echo "ERROR: compiled DSP binary missing: $dsp_src" >&2
  exit 1
fi
if [[ -e "$dsp_dst" ]]; then
  echo "Existing known-good DSP binary is PRESERVED: $dsp_dst"
else
  install -m 0755 "$dsp_src" "$dsp_dst"
fi
sha256sum "$dsp_dst" | tee "$data_dir/dsp.sha256"
git -C "$home/projects/festimix-audio-bench" rev-parse HEAD > "$data_dir/dsp-git-commit.txt" || true
git -C "$home/projects/Festimix" rev-parse HEAD > "$data_dir/ui-git-commit.txt" || true
cat > "$data_dir/launch-options.txt" <<'OPTS'
--preroll 256 --stable-playback --smooth-capture --ultra-low-latency --sink-target 48 --source-target 48
OPTS

for unit in festimix-quantum.service festimix-tascam.service festimix-dsp.service festimix-route.service festimix-web.service; do
  cp "$repo_dir/deploy/headless-48/$unit" "$units_dir/$unit"
done
mkdir -p "$home/.local/bin"
install -m 0755 "$repo_dir/deploy/headless-48/ensure-quantum.sh" "$home/.local/bin/festimix-ensure-quantum"
install -m 0755 "$repo_dir/deploy/headless-48/route-loop.sh" "$home/.local/bin/festimix-route-loop"
install -m 0755 "$repo_dir/deploy/headless-48/wait-native.sh" "$home/.local/bin/festimix-wait-native"
systemctl --user daemon-reload

if systemctl --user is-enabled tascamd.service >/dev/null 2>&1; then
  echo "Disabling old user tascamd.service auto-start to avoid double USB ownership"
  systemctl --user disable tascamd.service
fi

# Enable means "run when lingering user manager starts at boot".
# Do not use --now: this machine may still be running the manual audio stack.
systemctl --user enable festimix-quantum.service festimix-tascam.service festimix-dsp.service festimix-route.service festimix-web.service
echo "Enabling systemd user lingering (this asks for sudo once)"
sudo loginctl enable-linger "$(id -un)"

echo
echo "Installed, but NOT started. Preserve your current audio session."
echo "Check: loginctl show-user $(id -un) -p Linger"
echo "For a clean manual switchover: stop old manual Node/DSP/Tascam processes,"
echo "then run: systemctl --user start festimix-quantum.service festimix-tascam.service festimix-dsp.service festimix-route.service festimix-web.service"
echo "Inspect: systemctl --user --no-pager status festimix-{tascam,dsp,route,web}.service"
echo "Wi-Fi and Ethernet configurations are NOT changed."
