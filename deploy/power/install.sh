#!/usr/bin/env bash
set -euo pipefail
user="$(id -un)"
home="$HOME"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "$root" != "$home/projects/tascam_us1641_linux" ]]; then
  echo "ERROR: repository must be at ~/projects/tascam_us1641_linux (systemd unit uses this exact path)" >&2
  exit 1
fi
if ! command -v visudo >/dev/null && ! [[ -x /usr/sbin/visudo ]]; then
  echo "ERROR: visudo unavailable" >&2
  exit 1
fi
sudo_command="$(command -v systemctl)"
if [[ "$sudo_command" != "/usr/bin/systemctl" ]]; then
  echo "ERROR: expected /usr/bin/systemctl, got $sudo_command" >&2
  exit 1
fi
mkdir -p "$home/.config/festimix-power" "$home/.config/systemd/user"
chmod 700 "$home/.config/festimix-power"
keypath="$home/.config/festimix-power/access-key"
existing_pin=""
if [[ -f "$keypath" ]]; then
  existing_pin="$(tr -d '\\r\\n' < "$keypath")"
fi
if [[ "$existing_pin" =~ ^[0-9]{4}$ ]]; then
  echo "Existing four-digit PIN preserved."
else
  echo "Set a new four-digit Festimix POWER PIN."
  if [[ -t 0 ]]; then
    while true; do
      read -r -s -p "Enter four digits (blank = random PIN): " pin
      echo
      if [[ -z "$pin" ]]; then
        pin="$(python3 -c 'import secrets; print(f"{secrets.randbelow(10000):04d}")')"
      fi
      if [[ "$pin" =~ ^[0-9]{4}$ ]]; then break; fi
      echo "PIN must contain exactly four digits."
    done
  else
    pin="$(python3 -c 'import secrets; print(f"{secrets.randbelow(10000):04d}")')"
  fi
  umask 077
  printf '%s\\n' "$pin" > "$keypath"
  echo "PIN saved."
fi
chmod 600 "$keypath"

# Only grant exactly one command; no shell, no blanket root or reboot privileges.
case "$user" in
  *[!a-zA-Z0-9_-]*|'') echo "Unexpected username" >&2; exit 1;;
esac
rule="$user ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff"
temp="$(mktemp)"
trap 'rm -f "$temp"' EXIT
printf '%s\n' "$rule" > "$temp"
sudo /usr/sbin/visudo -cf "$temp"
sudo install -o root -g root -m 0440 "$temp" /etc/sudoers.d/festimix-poweroff
sudo /usr/sbin/visudo -cf /etc/sudoers.d/festimix-poweroff
cp "$root/deploy/power/festimix-power.service" "$home/.config/systemd/user/festimix-power.service"
systemctl --user daemon-reload
systemctl --user enable --now festimix-power.service
echo
echo "Power panel enabled. Open http://<HP-IP>:3099/ from iPad."
echo "FOUR-DIGIT PIN (keep private; anyone with it on this LAN can power off the PC):"
cat "$keypath"
echo
echo "Five incorrect attempts lock PIN entry globally for 10 minutes, even across service restarts."\necho "This is plain HTTP; use only a trusted private Wi-Fi, not an untrusted/public network."
echo "The audio-related services remain unchanged."
