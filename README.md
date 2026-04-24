# downtime-monitor

Lightweight Python script that monitors internet connectivity and logs every outage and high-latency event to daily text files.

## Requirements

Python 3.10+ — no third-party dependencies.

## Usage

```sh
python monitor.py              # run in foreground (Ctrl+C to stop)
python monitor.py --daemon     # run detached in the background
python monitor.py --stop       # stop the background instance
```

## How it works

Every 5 seconds the script attempts a TCP connection to `8.8.8.8:53` (Google DNS) and `1.1.1.1:53` (Cloudflare DNS).

| Condition | Action |
| --- | --- |
| All targets unreachable | Records the outage start time |
| Connection restored after outage | Writes a downtime entry to the log |
| Ping > 100 ms | Writes a high-ping warning to the log |

## Configuration

Edit the constants at the top of `monitor.py`:

| Constant | Default | Description |
| --- | --- | --- |
| `CHECK_INTERVAL` | `5` | Seconds between probes |
| `SOCK_TIMEOUT` | `3` | TCP connect timeout (seconds) |
| `PING_OVER` | `100` | High-ping threshold (ms) |
| `DNS_TARGETS` | Google + Cloudflare | List of `(host, port)` targets |

## Log files

Logs are written to `logs/YYYYMMDD.txt` (one file per UTC day). All timestamps are UTC.

### Downtime entry

```text
2026-04-24 03:11:42 UTC -> 2026-04-24 03:14:05 UTC | duration: 143s
```

### Event entry

```text
2026-04-24 03:11:42 UTC | ⚠️ Internet DOWN at 2026-04-24 03:11:42 UTC
2026-04-24 07:45:01 UTC | 🐢 High ping 213ms (threshold: 100ms)
2026-04-24 08:00:00 UTC | 🟢 Monitor started
```

## Background mode

On **Windows**, `--daemon` re-launches the script as a fully detached `CREATE_NO_WINDOW` process and exits the parent shell immediately.

On **Linux/macOS**, `--daemon` performs a double-fork to detach from the terminal.

Both modes write the child PID to `monitor.pid` so `--stop` can terminate it later.
