#!/usr/bin/env python3
"""
Live RFID reader for the SICK RFU630 over its built-in HTTP API.

Polls the reader's Quickstart inventory endpoint and prints each tag's
EPC (as hex) and RSSI, deduplicating repeats. The EPC arrives from the
device as a decimal byte array and is converted to a hex string here.

NOTE: /api/QuickstartInventoryVar only returns data while the reader's
Quickstart mode is running (started from the web UI at http://<reader>/).
It's a commissioning/demo endpoint -- good for verifying reads, not the
intended path for a permanent headless service.

Usage:
    python3 rfu630_reader.py
    python3 rfu630_reader.py --host 192.168.0.20 --interval 0.3
    python3 rfu630_reader.py --all     # print every poll, not just new EPCs

Requires only the Python 3 standard library (uses urllib, no pip needed).
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error


def epc_hex(byte_list):
    """Convert a decimal byte array (e.g. [52,0,226,...]) to a hex string."""
    return "".join(f"{b:02X}" for b in byte_list)


def fetch_tags(url, timeout):
    """Return the list of tag dicts from the reader, or [] on any error."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(time.strftime("%H:%M:%S"), "ERR ", e)
        return []

    if payload.get("header", {}).get("status") != 0:
        print(time.strftime("%H:%M:%S"), "ERR ",
              payload.get("header", {}).get("message", "non-zero status"))
        return []

    return (payload.get("data", {})
                   .get("QuickstartInventoryVar", {})
                   .get("Tags") or [])


def main():
    ap = argparse.ArgumentParser(description="Live SICK RFU630 tag reader")
    ap.add_argument("--host", default="192.168.0.20",
                    help="reader IP/hostname (default: 192.168.0.20)")
    ap.add_argument("--interval", type=float, default=0.3,
                    help="seconds between polls (default: 0.3)")
    ap.add_argument("--timeout", type=float, default=2.0,
                    help="HTTP request timeout in seconds (default: 2.0)")
    ap.add_argument("--all", action="store_true",
                    help="print every read, not just newly-seen EPCs")
    args = ap.parse_args()

    # line-buffer stdout so output shows up live even when piped to a file
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    url = f"http://{args.host}/api/QuickstartInventoryVar"
    print(f"polling {url} every {args.interval}s -- Ctrl-C to stop")
    print("present a tag to the reader...\n")

    seen = {}
    try:
        while True:
            for t in fetch_tags(url, args.timeout):
                epc = epc_hex(t.get("EPC", []))
                if not epc:
                    continue  # skip empty/placeholder tag slots
                rssis = t.get("RSSIs") or [0]
                rssi = rssis[0]
                antenna = t.get("AntennaMask", "?")
                ts = time.strftime("%H:%M:%S")

                if epc not in seen:
                    print(ts, "NEW ", epc, f"{rssi} dBm", f"ant={antenna}")
                elif args.all:
                    print(ts, "    ", epc, f"{rssi} dBm", f"ant={antenna}")
                seen[epc] = rssi

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nstopped -- {len(seen)} unique tag(s) seen this session")
        for epc, rssi in seen.items():
            print("  ", epc, f"(last {rssi} dBm)")


if __name__ == "__main__":
    main()
