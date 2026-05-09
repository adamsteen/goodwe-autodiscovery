# goodwe-autodiscovery

Small Python helper for finding and reading local GoodWe inverter runtime data.

This project exists because some newer GoodWe dongles do not behave like older plaintext UDP devices. In particular, some Kit-20 dongles advertise `dtls_port:8899` from the discovery endpoint and then drop normal plaintext inverter requests. This script tries the upstream `goodwe.search_inverters()` path first, falls back to a directed UDP discovery probe, detects DTLS-capable dongles, and then connects with an explicit inverter family.

## Links

- Upstream library: [marcelblijleven/goodwe](https://github.com/marcelblijleven/goodwe)
- Relevant DTLS issue: [marcelblijleven/goodwe#121](https://github.com/marcelblijleven/goodwe/issues/121)
- DTLS comment with test command and branch: [issue comment](https://github.com/marcelblijleven/goodwe/issues/121#issuecomment-4344389702)

## Setup

Create and activate a virtual environment:

```sh
python -m venv .venv
source .venv/bin/activate
```

Install the DTLS-capable GoodWe branch:

```sh
python -m pip install -r requirements.txt
```

The current PyPI `goodwe` release may not support `dtls=True`. If your dongle advertises `dtls_port:8899`, use the branch in `requirements.txt`.

## Usage

Try autodiscovery:

```sh
python goodwe_autodiscover.py
```

Skip discovery and connect to a known inverter address:

```sh
python goodwe_autodiscover.py --host <inverter-ip>
```

Force DTLS explicitly:

```sh
python goodwe_autodiscover.py --host <inverter-ip> --dtls --family ET
```

Use a different directed broadcast address:

```sh
python goodwe_autodiscover.py --broadcast-host <subnet-broadcast-ip>
```

Increase only the fallback discovery wait time:

```sh
python goodwe_autodiscover.py --discovery-timeout 10
```

## Directed Discovery Fallback

`goodwe_autodiscover.py` includes a directed UDP discovery fallback using the same packet from the upstream issue comment:

```sh
python goodwe_autodiscover.py --broadcast-host <subnet-broadcast-ip> --discovery-timeout 10
```

A DTLS-capable dongle may reply with something like:

```text
dongle@sn,dtls_port:8899,<dongle-serial>
```

In that case the source address of the UDP reply is treated as the inverter host, and `goodwe_autodiscover.py` enables `dtls=True`.

## CLI Options

```text
--host              Inverter IP or hostname. Skips discovery when provided.
--port              Inverter communication port. Defaults to 8899.
--family            GoodWe inverter family. Defaults to ET.
--timeout           Timeout for inverter requests. Defaults to 1 second.
--dtls              Force DTLS mode.
--broadcast-host    Directed broadcast address for fallback discovery.
--discovery-port    UDP discovery port. Defaults to 48899.
--discovery-timeout Timeout for directed fallback discovery. Defaults to 1 second.
```

## Notes

- `dtls=True` requires an explicit inverter family, so this tool defaults `--family` to `ET`.
- Autodiscovery still starts with upstream plaintext discovery. If that fails, the directed UDP fallback probes the configured broadcast address.
- The project is a local diagnostic/helper script, not a replacement for the upstream `goodwe` package.
