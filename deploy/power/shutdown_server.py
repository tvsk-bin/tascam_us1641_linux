#!/usr/bin/env python3
"""Standalone, authenticated LAN-only poweroff UI for Festimix headless HP.

No third-party dependencies. No audio configuration change.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
from urllib.parse import urlsplit

PORT = int(os.environ.get("FESTIMIX_POWER_PORT", "3099"))
SECRET_FILE = Path.home() / ".config" / "festimix-power" / "access-key"
KEY = SECRET_FILE.read_text(encoding="utf-8").strip()
if len(KEY) != 4 or not KEY.isascii() or not KEY.isdecimal():
    raise SystemExit("Power controller requires a four-digit PIN. Re-run deploy/power/install.sh")
# Global lockout survives web service restart. Applies to all clients on the LAN.
LIMIT_FILE = SECRET_FILE.parent / "pin-attempts.json"
MAX_FAILED = 5
LOCKOUT_SECONDS = 600
def load_limits():
    try:
        state = json.loads(LIMIT_FILE.read_text(encoding="utf-8"))
        return {"failures": max(0, int(state.get("failures", 0))),
                "locked_until": float(state.get("locked_until", 0))}
    except (OSError, ValueError, TypeError):
        return {"failures": 0, "locked_until": 0}

LIMITS = load_limits()
def save_limits():
    tmp = LIMIT_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(LIMITS, output)
    os.replace(tmp, LIMIT_FILE)
CHALLENGES = {}
LOCK = threading.Lock()
POWER_COMMAND = ["/usr/bin/sudo", "-n", "/usr/bin/systemctl", "poweroff"]

PAGE = """<!doctype html><html lang="hu"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer"><title>Festimix · Power</title>
<style>
:root { color-scheme: dark } *{box-sizing:border-box}
body{font:16px system-ui,sans-serif;background:#101418;color:#eef2f6;display:grid;place-items:center;min-height:100dvh;margin:0;padding:18px}
main{width:min(460px,100%);padding:28px;border:1px solid #39414c;border-radius:18px;background:#1b222a}
h1{margin:0 0 10px;font-size:25px}p{line-height:1.45;color:#b9c5cf}
label{display:block;margin:24px 0 8px}input{width:100%;padding:15px;border:1px solid #576471;border-radius:10px;font-size:17px;background:#101418;color:white}
button{font:inherit;border:1px solid #626f7c;border-radius:12px;background:#33404c;color:white;padding:15px 20px;min-height:54px;cursor:pointer;width:100%;margin-top:14px}
button:disabled{opacity:.5;cursor:not-allowed}.danger{background:#953b37;border-color:#bd5b55;font-weight:700}
#confirm{display:none;margin-top:16px;border-top:1px solid #43505a;padding-top:14px}
#status{min-height:24px}small{color:#aab5c2}
</style></head><body><main>
<h1>Festimix · POWER</h1>
<p>HP mini PC szabályos leállítása. A keverő hangja és az iPad-kapcsolat megszakad.</p>
<label for="key">4 jegyű PIN</label><input id="key" type="password" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" autocomplete="off" spellcheck="false">
<button id="prepare">SHUTDOWN</button>
<section id="confirm"><p>Biztosan leállítod a teljes Festimix gépet?</p>
<button id="sure" class="danger" disabled>SURE · 5</button>
<button id="cancel">CANCEL</button></section>
<p id="status" role="status"></p><small>Ez nem a keverő újraindítása. Visszakapcsoláshoz a HP fizikai bekapcsológombja szükséges.</small>
</main><script>
"use strict";
const $=id=>document.getElementById(id);let nonce="",deadline=0,timer=null;
const status=text=>$("status").textContent=text;
function clearConfirm(){nonce="";deadline=0;clearInterval(timer);timer=null;$("confirm").style.display="none";$("prepare").disabled=false}
async function send(url,body){
 const res=await fetch(url,{method:"POST",credentials:"same-origin",cache:"no-store",
 headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
 const obj=await res.json().catch(()=>({error:"No response"}));
 if(!res.ok)throw Error(obj.error||"Request failed");
 return obj;
}
$("prepare").onclick=async()=>{
 clearConfirm();
 try{
  if(!/^[0-9]{4}$/.test($("key").value)){status("Négy számjegyet adj meg.");return}
  const response=await send("/prepare",{key:$("key").value});
  nonce=response.nonce;deadline=Date.now()+5000;
  $("confirm").style.display="block";$("prepare").disabled=true;
  $("sure").disabled=true;status("Megerősítés szükséges.");
  timer=setInterval(()=>{let n=Math.max(0,Math.ceil((deadline-Date.now())/1000));
   $("sure").textContent=n?"SURE · "+n:"SURE · SHUTDOWN";
   $("sure").disabled=n>0;},100);
 }catch(err){status(err.message)}
};
$("cancel").onclick=()=>{clearConfirm();status("Leállítás megszakítva.")};
$("sure").onclick=async()=>{
 if(!nonce||Date.now()<deadline)return;
 $("sure").disabled=true;
 try{await send("/execute",{key:$("key").value,nonce});
  status("Leállítás elindítva. A kapcsolat megszakad.");clearConfirm();
 }catch(err){status(err.message);clearConfirm()}
};
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    server_version = "FestimixPower/1.0"
    def log_message(self, fmt, *args):
        print("%s %s" % (self.address_string(), fmt % args), flush=True)
    def respond(self, code, data):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)
    def do_GET(self):
        if self.path != "/":
            self.send_error(404);return
        body=PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","no-referrer")
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        if self.path not in ("/prepare","/execute"):
            self.respond(404,{"error":"Not found"});return
        # Browser same-origin guard (CSRF) plus a rate-limited 4-digit PIN.
        origin=self.headers.get("Origin")
        host=self.headers.get("Host","")
        if not host or not origin or urlsplit(origin).netloc != host or urlsplit(origin).scheme != "http":
            self.respond(403,{"error":"Invalid origin"});return
        if self.headers.get("Content-Type","").split(";")[0].strip() != "application/json":
            self.respond(415,{"error":"JSON required"});return
        try:
            length=int(self.headers.get("Content-Length","0"))
            if length < 2 or length > 1024:
                raise ValueError("Invalid length")
            data=json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self.respond(400,{"error":"Invalid request"});return
        if not isinstance(data, dict):
            self.respond(400, {"error": "Invalid request"}); return
        supplied = str(data.get("key", ""))
        with LOCK:
            now_wall = time.time()
            if LIMITS["locked_until"] > now_wall:
                self.respond(429, {"error": "Túl sok próbálkozás. Próbáld újra 10 perc múlva."})
                return
            if not hmac.compare_digest(supplied, KEY):
                LIMITS["failures"] += 1
                if LIMITS["failures"] >= MAX_FAILED:
                    LIMITS["locked_until"] = now_wall + LOCKOUT_SECONDS
                    LIMITS["failures"] = 0
                save_limits()
                self.respond(403, {"error": "Hibás PIN"})
                return
            LIMITS["failures"] = 0
            LIMITS["locked_until"] = 0
            save_limits()
        now=time.monotonic()
        with LOCK:
            for token,(_,expiry) in list(CHALLENGES.items()):
                if expiry<now: CHALLENGES.pop(token,None)
            if self.path=="/prepare":
                token=secrets.token_urlsafe(24)
                CHALLENGES.clear()
                CHALLENGES[token]=(now+5.0,now+45.0)
                self.respond(200,{"nonce":token})
                return
            token=str(data.get("nonce",""))
            entry=CHALLENGES.pop(token,None)
            if not entry or not entry[0]<=now<=entry[1]:
                self.respond(409,{"error":"Confirmation missing, too early or expired"});return
        self.respond(200,{"ok":True,"status":"poweroff-requested"})
        def poweroff():
            time.sleep(1.0)
            result=subprocess.run(POWER_COMMAND,capture_output=True,text=True,timeout=10)
            if result.returncode:print("poweroff failed:",result.stderr,flush=True)
        threading.Thread(target=poweroff,daemon=True).start()

if __name__=="__main__":
    print(f"Festimix power controller on TCP {PORT} (LAN access; HTTP not encrypted)",flush=True)
    ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
