#!/usr/bin/env python3
"""Operator dashboard for `make daemon-status`."""

import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PIKA_DIR = SCRIPT_DIR.parent
YAML_PATH = PIKA_DIR / "pika.yaml"
DATA_DIR = PIKA_DIR / "datalogger" / "data"
SCOPE_SHM_PATH = Path("/dev/shm/pika_scope_shm")
SCOPE_MAGIC = 0x5C09E000
REMOTEPROC = Path("/sys/class/remoteproc")
HEALTH_URL = "http://127.0.0.1:8888/health"
WEB_PORT = 8888
UNIT = "pika-run-all.service"
BOX = 68
ANSI_RE = re.compile(r"\033\[[0-9;]*m")

WORDMARK = [
    r"   _____  _  _             _____  _        _",
    r"  |  __ \(_)| |           / ____|| |      | |",
    r"  | |__) | || | __  __ _ | (___  | |_ __ _| |_ _   _ ___",
    r"  |  ___/ | || |/ / / _` | \___ \ | __/ _` | __| | | / __|",
    "  | |     | ||   < | (_| | ____) || || (_| | |_| |_| \\__ \\",
    "  |_|     |_||_|\\_\\ \\__,_||_____/  \\__\\__,_|\\__|\\__,_|___/",
]


def visible_len(text):
    return len(ANSI_RE.sub("", text))


class Theme(object):
    def __init__(self):
        no_color = os.environ.get("NO_COLOR", "") != ""
        term = os.environ.get("TERM", "") or ""
        colorterm = os.environ.get("COLORTERM", "") or ""
        tty = sys.stdout.isatty()
        self.enabled = tty and not no_color and term != "dumb"
        self.xterm256 = self.enabled and (
            "256color" in term
            or colorterm != ""
            or term.startswith(("xterm", "screen", "tmux", "vt220"))
        )
        enc = (sys.stdout.encoding or "").lower()
        self.unicode = tty and "utf" in enc

    def _fg256(self, n):
        return "\033[38;5;%dm" % n

    def _fg16(self, n):
        return "\033[%dm" % n

    def fg(self, n256, n16):
        if not self.enabled:
            return ""
        if self.xterm256:
            return self._fg256(n256)
        return self._fg16(n16)

    def reset(self):
        return "\033[0m" if self.enabled else ""

    @property
    def gold(self):
        return self.fg(220, 93)

    @property
    def title(self):
        return self.fg(75, 96)

    @property
    def border(self):
        return self.fg(240, 90)

    @property
    def label(self):
        return self.fg(245, 90)

    @property
    def value(self):
        return self.fg(252, 97)

    @property
    def ok(self):
        return self.fg(82, 92)

    @property
    def warn(self):
        return self.fg(214, 93)

    @property
    def bad(self):
        return self.fg(196, 91)

    @property
    def accent(self):
        return self.fg(81, 96)

    @property
    def dim(self):
        return self.fg(244, 90)


def paint(theme, color, text):
    if not text:
        return ""
    return color + text + theme.reset()


def run_cmd(args, timeout=2.5, use_sudo_n=False):
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            universal_newlines=True,
        )
        if proc.returncode == 0:
            return proc.stdout
        if use_sudo_n and args[0] != "sudo":
            return run_cmd(["sudo", "-n"] + args, timeout=timeout, use_sudo_n=False)
        return ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return ""


def resource_tone(theme, pct):
    if pct is None:
        return theme.dim
    if pct >= 90:
        return theme.bad
    if pct >= 70:
        return theme.warn
    return theme.ok


def status_tone(theme, kind, text):
    raw = (text or "").lower()
    if raw in ("n/a", ""):
        return theme.dim
    if kind == "pru1" and raw == "offline":
        return theme.warn
    if raw in ("running", "active", "enabled", "ok", "present"):
        return theme.ok
    if raw in ("idle", "offline", "activating", "degraded"):
        return theme.warn
    if raw in ("failed", "error", "stopped", "disabled", "dead"):
        return theme.bad
    return theme.value


def collect_systemd():
    info = {
        "active": None,
        "sub": None,
        "enabled": None,
        "restarts": None,
        "pid": None,
        "since": None,
        "failed": False,
    }
    out = run_cmd(
        [
            "systemctl",
            "show",
            UNIT,
            "--property=ActiveState,SubState,UnitFileState,NRestarts,MainPID,ActiveEnterTimestamp",
        ],
        use_sudo_n=True,
    )
    if not out:
        return info
    parsed = {}
    for line in out.splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            parsed[key] = val.strip()
    info["active"] = parsed.get("ActiveState") or None
    info["sub"] = parsed.get("SubState") or None
    info["enabled"] = parsed.get("UnitFileState") or None
    restarts = parsed.get("NRestarts")
    info["restarts"] = restarts if restarts != "" else None
    pid = parsed.get("MainPID")
    info["pid"] = pid if pid and pid != "0" else None
    since = parsed.get("ActiveEnterTimestamp")
    if since and since not in ("n/a", "0"):
        info["since"] = since
    info["failed"] = info["active"] in ("failed", "activating")
    return info


def collect_journal():
    out = run_cmd(
        ["journalctl", "-u", UNIT, "-n", "5", "--no-pager"],
        use_sudo_n=True,
        timeout=3.0,
    )
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    return lines[-5:]


def _pru_match(name, core):
    lowered = name.lower()
    if core == 0:
        return "4a334000.pru" in lowered or lowered == "pru0"
    return "4a338000" in lowered or lowered == "pru1"


def collect_pru(core):
    result = {"name": None, "state": None, "firmware": None}
    if not REMOTEPROC.is_dir():
        return result
    try:
        entries = sorted(REMOTEPROC.glob("remoteproc*"))
    except OSError:
        return result
    for entry in entries:
        name = read_text(entry / "name")
        if not name or not _pru_match(name, core):
            continue
        result["name"] = name
        result["state"] = read_text(entry / "state") or None
        result["firmware"] = read_text(entry / "firmware") or None
        return result
    return result


def collect_pids(pattern, exact=False):
    args = ["pgrep", "-x", pattern] if exact else ["pgrep", "-f", pattern]
    out = run_cmd(args)
    pids = [p for p in out.split() if p.isdigit()]
    return pids


def port_open(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.4)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def collect_health():
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = getattr(resp, "status", 200)
        return json.loads(body), status
    except (urllib.error.URLError, socket.timeout, ValueError, OSError):
        return None, None


def collect_scope_shm():
    info = {"ok": False, "magic": None, "sample_rate": None, "total": None}
    if not SCOPE_SHM_PATH.exists():
        return info
    try:
        with SCOPE_SHM_PATH.open("rb") as fh:
            header = fh.read(32)
        if len(header) < 32:
            return info
        magic, rate, _ch, _cap, _clk, _period, total = struct.unpack(
            "<IIIIIIQ", header
        )
        info["magic"] = "0x%08x" % magic
        info["sample_rate"] = rate
        info["total"] = total
        info["ok"] = magic == SCOPE_MAGIC
    except OSError:
        pass
    return info


def collect_yaml():
    values = {}
    if not YAML_PATH.is_file():
        return values
    wanted = {"nominal_rate_hz", "ac_freq_hz", "target_mains_vrms"}
    wanted.update("ch%d_enable" % i for i in range(8))
    try:
        for line in YAML_PATH.read_text().splitlines():
            raw = line.split("#", 1)[0]
            if ":" not in raw:
                continue
            key, val = raw.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key in wanted and val:
                values[key] = val
    except OSError:
        pass
    return values


def collect_host():
    host = {
        "hostname": None,
        "uptime": None,
        "load": None,
        "cpu_pct": None,
        "mem": None,
        "mem_pct": None,
        "disk": None,
        "disk_pct": None,
        "ips": None,
        "data_size": None,
    }
    host["hostname"] = run_cmd(["hostname"]).strip() or read_text("/etc/hostname") or None
    uptime = run_cmd(["uptime", "-p"]).strip()
    if uptime.startswith("up "):
        uptime = uptime[3:]
    if not uptime and Path("/proc/uptime").is_file():
        first = read_text("/proc/uptime").split()
        if first:
            try:
                mins = int(float(first[0]) / 60)
                if mins >= 60:
                    uptime = "%dh %dm" % (mins // 60, mins % 60)
                else:
                    uptime = "%dm" % mins
            except ValueError:
                uptime = ""
    host["uptime"] = uptime or None

    if Path("/proc/loadavg").is_file():
        parts = read_text("/proc/loadavg").split()
        if len(parts) >= 3:
            host["load"] = " ".join(parts[:3])

    if Path("/proc/stat").is_file():
        def cpu_pair():
            fields = read_text("/proc/stat").splitlines()
            if not fields:
                return None
            cols = fields[0].split()
            if len(cols) < 5:
                return None
            nums = [int(x) for x in cols[1:8]]
            idle = nums[3]
            total = sum(nums)
            return idle, total

        first = cpu_pair()
        time.sleep(0.5)
        second = cpu_pair()
        if first and second:
            di = second[0] - first[0]
            dt = second[1] - first[1]
            if dt > 0:
                host["cpu_pct"] = (1.0 - (float(di) / dt)) * 100.0

    mem_out = run_cmd(["free", "-m"])
    for line in mem_out.splitlines():
        if line.startswith("Mem:"):
            cols = line.split()
            if len(cols) >= 3:
                try:
                    total = float(cols[1])
                    used = float(cols[2])
                    if total > 0:
                        host["mem_pct"] = (used / total) * 100.0
                        host["mem"] = "%d%% of %dMB (%dMB used)" % (
                            int(round(host["mem_pct"])),
                            int(total),
                            int(used),
                        )
                except ValueError:
                    pass
            break

    disk_out = run_cmd(["df", "-h", "/"])
    lines = disk_out.splitlines()
    if len(lines) >= 2:
        cols = lines[1].split()
        if len(cols) >= 5:
            used_s = cols[4].rstrip("%")
            try:
                host["disk_pct"] = float(used_s)
            except ValueError:
                host["disk_pct"] = None
            host["disk"] = "%s of %s (%s used)" % (cols[4], cols[1], cols[2])

    ips = run_cmd(["hostname", "-I"]).strip()
    v4 = [tok for tok in ips.split() if tok and ":" not in tok]
    if not v4:
        ip_out = run_cmd(["ip", "-4", "-o", "addr", "show", "scope", "global"])
        for line in ip_out.splitlines():
            parts = line.split()
            if "inet" in parts:
                idx = parts.index("inet")
                if idx + 1 < len(parts):
                    v4.append(parts[idx + 1].split("/")[0])
    host["ips"] = " ".join(v4) or None

    if DATA_DIR.is_dir():
        du = run_cmd(["du", "-sh", str(DATA_DIR)], timeout=8.0)
        if du:
            host["data_size"] = du.split()[0]
    return host


def enabled_channels(yaml_vals):
    names = []
    for i in range(8):
        flag = str(yaml_vals.get("ch%d_enable" % i, "0")).strip()
        if flag in ("1", "true", "True", "yes"):
            names.append("CH%d" % i)
    return names


def format_rate(value):
    if value is None or value == "":
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num == 0:
        return "free-run"
    if num >= 1000 and abs(num - round(num)) < 0.05:
        return "%d Hz" % int(round(num))
    if abs(num - round(num)) < 0.05:
        return "%d Hz" % int(round(num))
    return "%.1f Hz" % num


def format_samples(total):
    if total is None:
        return None
    try:
        n = int(total)
    except (TypeError, ValueError):
        return str(total)
    if n >= 1_000_000_000:
        return "%.2fe9" % (n / 1e9)
    if n >= 1_000_000:
        return "{:,}".format(n)
    return "{:,}".format(n)


def format_learned(value, unit):
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if unit == "V":
        return "%.1f Vrms" % num
    if abs(num - round(num)) < 0.05:
        return "%d" % int(round(num))
    return "%.1f" % num


def hline(theme, title=None):
    if theme.unicode:
        if title:
            prefix = "┌─ " + title + " "
            fill = BOX - 1 - visible_len(prefix)
            if fill < 1:
                fill = 1
            body = prefix + ("─" * fill) + "┐"
        else:
            body = "└" + ("─" * (BOX - 2)) + "┘"
    else:
        if title:
            prefix = "+-- " + title + " "
            fill = BOX - 1 - len(prefix)
            if fill < 1:
                fill = 1
            body = prefix + ("-" * fill) + "+"
        else:
            body = "+" + ("-" * (BOX - 2)) + "+"
    return paint(theme, theme.border, body)


def row(theme, content):
    inner = BOX - 6
    extra = inner - visible_len(content)
    if extra < 0:
        extra = 0
    if theme.unicode:
        left, right = "│  ", "  │"
    else:
        left, right = "|  ", "  |"
    return (
        paint(theme, theme.border, left)
        + content
        + (" " * extra)
        + paint(theme, theme.border, right)
    )


def pair(theme, left_label, left_value, left_color, right_label, right_value, right_color):
    left = (
        paint(theme, theme.label, "%-12s" % left_label)
        + paint(theme, left_color, left_value)
    )
    right = (
        paint(theme, theme.label, "%-10s" % right_label)
        + paint(theme, right_color, right_value)
    )
    gap = 4
    pad = 28 - visible_len(left)
    if pad < 1:
        pad = 1
    return left + (" " * pad) + right if right_label else left


def collect_all():
    systemd = collect_systemd()
    health, health_status = collect_health()
    yaml_vals = collect_yaml()
    scope = collect_scope_shm()
    dl_pids = collect_pids("datalogger", exact=True)
    web_pids = collect_pids("uvicorn")
    listening = port_open(WEB_PORT)
    return {
        "systemd": systemd,
        "health": health or {},
        "health_status": health_status,
        "yaml": yaml_vals,
        "scope": scope,
        "pru0": collect_pru(0),
        "pru1": collect_pru(1),
        "dl_pids": dl_pids,
        "web_pids": web_pids,
        "listening": listening,
        "host": collect_host(),
        "journal": collect_journal() if systemd.get("failed") else [],
    }


def render(theme, data):
    lines = []
    gold = theme.gold
    for banner in WORDMARK:
        lines.append(paint(theme, gold, banner))

    host = data["host"]
    hostname = host.get("hostname") or "n/a"
    uptime = host.get("uptime") or "n/a"
    ips = host.get("ips") or "n/a"
    subtitle_left = (
        paint(theme, theme.value, hostname)
        + paint(theme, theme.dim, "   up ")
        + paint(theme, theme.value, uptime)
    )
    subtitle_right = paint(theme, theme.accent, ips)
    gap = BOX - visible_len(subtitle_left) - visible_len(subtitle_right)
    if gap < 2:
        gap = 2
    lines.append("  " + subtitle_left + (" " * gap) + subtitle_right)
    lines.append("")

    # Service
    sd = data["systemd"]
    active = sd.get("active") or "n/a"
    sub = sd.get("sub")
    state = active if not sub or active == "n/a" else (
        "%s (%s)" % (active, sub) if active != sub else active
    )
    enabled = sd.get("enabled") or "n/a"
    restarts = sd.get("restarts") if sd.get("restarts") is not None else "n/a"
    pid = sd.get("pid") or "n/a"
    since = sd.get("since") or "n/a"
    state_color = status_tone(theme, "svc", active)
    if active == "active" and sub == "running":
        state_color = theme.ok
    lines.append(hline(theme, "service"))
    svc_left = (
        paint(theme, theme.value, "pika-run-all")
        + "   "
        + paint(theme, state_color, state)
        + "   "
        + paint(theme, status_tone(theme, "svc", enabled), enabled)
    )
    svc_right = (
        paint(theme, theme.label, "restarts ")
        + paint(theme, theme.warn if str(restarts) not in ("0", "n/a") else theme.value, str(restarts))
        + "   "
        + paint(theme, theme.label, "pid ")
        + paint(theme, theme.accent if pid != "n/a" else theme.dim, str(pid))
    )
    pad = BOX - 6 - visible_len(svc_left) - visible_len(svc_right)
    if pad < 2:
        pad = 2
    lines.append(row(theme, svc_left + (" " * pad) + svc_right))
    lines.append(
        row(
            theme,
            paint(theme, theme.label, "since        ")
            + paint(theme, theme.value if since != "n/a" else theme.dim, since),
        )
    )
    lines.append(hline(theme))
    lines.append("")

    # Components
    lines.append(hline(theme, "components"))
    for core, key, kind in ((0, "pru0", "pru0"), (1, "pru1", "pru1")):
        pru = data[key]
        state = pru.get("state") or "n/a"
        name = pru.get("name") or "n/a"
        fw = pru.get("firmware")
        fw_s = ("fw " + fw) if fw else ""
        label = "PRU%d" % core
        content = (
            paint(theme, theme.label, "%-12s" % label)
            + paint(theme, status_tone(theme, kind, state), "%-10s" % state)
            + paint(theme, theme.value if name != "n/a" else theme.dim, name)
        )
        if fw_s:
            content += "   " + paint(theme, theme.dim, fw_s)
        lines.append(row(theme, content))

    health = data["health"]
    dl_pids = data["dl_pids"]
    if health.get("datalogger_running"):
        dl_state, dl_kind = "running", "running"
    elif dl_pids:
        dl_state, dl_kind = "idle", "idle"
    elif data["systemd"].get("active") == "active":
        dl_state, dl_kind = "stopped", "stopped"
    elif dl_pids == [] and not REMOTEPROC.is_dir():
        dl_state, dl_kind = "n/a", "n/a"
    else:
        dl_state, dl_kind = "stopped", "stopped"
    dl_pid = dl_pids[0] if dl_pids else "n/a"
    lines.append(
        row(
            theme,
            paint(theme, theme.label, "%-12s" % "Datalogger")
            + paint(theme, status_tone(theme, "dl", dl_kind), "%-10s" % dl_state)
            + paint(theme, theme.label, "pid ")
            + paint(theme, theme.accent if dl_pid != "n/a" else theme.dim, str(dl_pid)),
        )
    )

    web_pids = data["web_pids"]
    health_status = data["health_status"]
    if health_status == 200:
        web_state, web_kind = "running", "running"
        health_txt = "/health ok"
        health_color = theme.ok
    elif data["listening"] or web_pids:
        web_state, web_kind = "degraded", "idle"
        health_txt = "/health down"
        health_color = theme.bad
    elif data["systemd"].get("active") == "active":
        web_state, web_kind = "stopped", "stopped"
        health_txt = "/health down"
        health_color = theme.bad
    else:
        web_state, web_kind = "n/a", "n/a"
        health_txt = "n/a"
        health_color = theme.dim
    lines.append(
        row(
            theme,
            paint(theme, theme.label, "%-12s" % "Webserver")
            + paint(theme, status_tone(theme, "web", web_kind), "%-10s" % web_state)
            + paint(theme, theme.accent, ":%d" % WEB_PORT)
            + "   "
            + paint(theme, health_color, health_txt),
        )
    )
    lines.append(hline(theme))
    lines.append("")

    # Acquisition
    yaml_vals = data["yaml"]
    scope = data["scope"]
    cfg_rate = health.get("sample_rate") or yaml_vals.get("nominal_rate_hz")
    actual = health.get("actual_sample_rate")
    if actual in (0, 0.0, None, ""):
        actual = None
    chans = enabled_channels(yaml_vals)
    mains = yaml_vals.get("ac_freq_hz")
    shm_magic = health.get("shm_magic") or scope.get("magic")
    shm_ok = False
    if scope.get("ok"):
        shm_ok = True
    elif isinstance(shm_magic, str) and "5c09e000" in shm_magic.lower():
        shm_ok = True
    shm_state = "ok" if shm_ok else ("n/a" if not shm_magic else "bad")
    samples = health.get("total_samples")
    if samples is None:
        samples = scope.get("total")
    learned_v = health.get("learned_voltage")
    learned_r = health.get("learned_transformer_ratio")

    lines.append(hline(theme, "acquisition"))
    lines.append(
        row(
            theme,
            pair(
                theme,
                "Rate",
                format_rate(cfg_rate) or "n/a",
                theme.value if cfg_rate not in (None, "") else theme.dim,
                "actual",
                format_rate(actual) or "n/a",
                theme.value if actual is not None else theme.dim,
            ),
        )
    )
    lines.append(
        row(
            theme,
            pair(
                theme,
                "Channels",
                " ".join(chans) if chans else "n/a",
                theme.value if chans else theme.dim,
                "mains",
                ("%s Hz" % mains) if mains else "n/a",
                theme.value if mains else theme.dim,
            ),
        )
    )
    shm_color = theme.ok if shm_state == "ok" else (theme.bad if shm_state == "bad" else theme.dim)
    lines.append(
        row(
            theme,
            pair(
                theme,
                "Scope SHM",
                shm_state,
                shm_color,
                "samples",
                format_samples(samples) or "n/a",
                theme.value if samples is not None else theme.dim,
            ),
        )
    )
    lines.append(
        row(
            theme,
            pair(
                theme,
                "Learned",
                format_learned(learned_v, "V") or "n/a",
                theme.value if learned_v is not None else theme.dim,
                "ratio",
                format_learned(learned_r, "") or "n/a",
                theme.value if learned_r is not None else theme.dim,
            ),
        )
    )
    lines.append(hline(theme))
    lines.append("")

    # Resources
    cpu = host.get("cpu_pct")
    mem = host.get("mem") or "n/a"
    disk = host.get("disk") or "n/a"
    load = host.get("load") or "n/a"
    data_size = host.get("data_size") or "n/a"
    cpu_s = "%.1f%%" % cpu if cpu is not None else "n/a"
    lines.append(hline(theme, "resources"))
    lines.append(
        row(
            theme,
            pair(
                theme,
                "CPU",
                cpu_s,
                resource_tone(theme, cpu),
                "load",
                load,
                theme.value if load != "n/a" else theme.dim,
            ),
        )
    )
    lines.append(
        row(
            theme,
            paint(theme, theme.label, "%-12s" % "Mem")
            + paint(theme, resource_tone(theme, host.get("mem_pct")), mem),
        )
    )
    disk_line = (
        paint(theme, theme.label, "%-12s" % "Disk /")
        + paint(theme, resource_tone(theme, host.get("disk_pct")), disk)
    )
    data_bit = (
        paint(theme, theme.label, "    data ")
        + paint(theme, theme.value if data_size != "n/a" else theme.dim, data_size)
    )
    gap = BOX - 6 - visible_len(disk_line) - visible_len(data_bit)
    if gap < 2:
        gap = 2
    lines.append(row(theme, disk_line + (" " * gap) + data_bit))
    lines.append(
        row(
            theme,
            paint(theme, theme.label, "%-12s" % "IP")
            + paint(theme, theme.accent if ips != "n/a" else theme.dim, ips),
        )
    )
    lines.append(hline(theme))

    if data["journal"]:
        lines.append("")
        lines.append(paint(theme, theme.warn, "  recent journal"))
        for item in data["journal"]:
            lines.append(paint(theme, theme.dim, "  " + item))

    return "\n".join(lines)


def main():
    theme = Theme()
    try:
        data = collect_all()
        print(render(theme, data))
        print(theme.reset(), end="")
    except BrokenPipeError:
        pass
    finally:
        if theme.enabled:
            try:
                sys.stdout.write("\033[0m")
                sys.stdout.flush()
            except Exception:
                pass


if __name__ == "__main__":
    main()
