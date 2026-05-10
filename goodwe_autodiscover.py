import argparse
import asyncio
import ipaddress
import inspect
import re
import socket

import goodwe

def handle_max_retries_exception():
    print("No GoodWe inverter responded to network discovery.")
    print("Check that your computer is on the same network as the inverter and that UDP broadcast is allowed.")


def handle_directed_broadcast_timeout(broadcast_host, discovery_port, discovery_timeout):
    print(f"No reply from directed UDP broadcast to {broadcast_host}:{discovery_port} within {discovery_timeout} seconds.")
    print("Try a different --broadcast-host if your Mac is on a different subnet.")


def handle_permission_error():
    print("Python was not allowed to send the GoodWe network request.")
    print("Check your macOS local network/firewall permissions, VPN, or router UDP broadcast settings.")


def handle_inverter_error(error):
    print("Unable to connect to the GoodWe inverter.")
    print(error)


def handle_unsupported_dtls():
    print("This inverter dongle advertises DTLS, but the installed goodwe package does not support dtls=True.")
    print('Install the DTLS branch with: python -m pip install "goodwe[dtls] @ git+https://github.com/botts7/goodwe.git@feature/dtls-transport"')


def handle_discovery_parse_error(discovery_response):
    print("GoodWe network discovery responded, but no inverter IP address could be found.")
    print(f"Raw discovery response: {discovery_response!r}")


def extract_inverter_host(discovery_response, source_host=None):
    match = re.search(rb"\b(?:\d{1,3}\.){3}\d{1,3}\b", discovery_response)
    if not match:
        return source_host
    return match.group(0).decode("ascii")


def discovery_response_uses_dtls(discovery_response):
    return b"dtls_port:" in discovery_response


def get_default_broadcast_host():
    return str(ipaddress.ip_network("192.168.1.0/24").broadcast_address)


def search_inverters_with_directed_broadcast(broadcast_host, discovery_port, timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)

    try:
        sock.sendto(b"WIFIKIT-214028-READ", (broadcast_host, discovery_port))
        data, address = sock.recvfrom(2048)
        return data, address[0]
    except TimeoutError:
        return None, None
    finally:
        sock.close()


async def connect_inverter(host, port, family, timeout, dtls):
    connect_params = inspect.signature(goodwe.connect).parameters
    supports_dtls = "dtls" in connect_params

    if dtls and not supports_dtls:
        handle_unsupported_dtls()
        return None

    kwargs = {"port": port, "family": family, "timeout": timeout}
    if dtls:
        kwargs["dtls"] = True

    return await goodwe.connect(host, **kwargs)


async def find_inverter(port, family, timeout, dtls, broadcast_host, discovery_port, discovery_timeout):
    try:
        discovery_response = await goodwe.search_inverters()
        source_host = None
    except goodwe.exceptions.MaxRetriesException:
        print("GoodWe library discovery timed out; trying directed UDP broadcast.")
        discovery_response, source_host = search_inverters_with_directed_broadcast(
            broadcast_host,
            discovery_port,
            discovery_timeout,
        )
        if discovery_response is None:
            handle_directed_broadcast_timeout(broadcast_host, discovery_port, discovery_timeout)
            return None

    host = extract_inverter_host(discovery_response, source_host)
    if host is None:
        handle_discovery_parse_error(discovery_response)
        return None

    if discovery_response_uses_dtls(discovery_response):
        print("Discovery response advertises DTLS; using dtls=True.")
        dtls = True

    print(f"Found inverter at {host}:{port}")
    return await connect_inverter(host, port, family, timeout, dtls)


async def get_runtime_data(inverter):
    runtime_data = await inverter.read_runtime_data()

    for sensor in inverter.sensors():
        if sensor.id_ in runtime_data:
            print(f"{sensor.id_}: \t\t {sensor.name} = {runtime_data[sensor.id_]} {sensor.unit}")


def print_inverter_info(inverter):
    fields = (
        ("Model", inverter.model_name),
        ("Serial number", inverter.serial_number),
        ("Rated power", inverter.rated_power),
        ("AC output type", inverter.ac_output_type),
        ("Firmware", inverter.firmware),
        ("ARM firmware", inverter.arm_firmware),
        ("Modbus version", inverter.modbus_version),
        ("DSP1 version", inverter.dsp1_version),
        ("DSP2 version", inverter.dsp2_version),
        ("DSP SVN version", inverter.dsp_svn_version),
        ("ARM version", inverter.arm_version),
        ("ARM SVN version", inverter.arm_svn_version),
    )

    print("Inverter information:")
    for label, value in fields:
        if value is not None:
            print(f"{label}: {value}")
    print()


async def main(host=None, port=8899, family="ET", timeout=1, dtls=False, broadcast_host=None, discovery_port=48899, discovery_timeout=1):
    try:
        if host:
            print(f"Connecting to inverter at {host}:{port}")
            inverter = await connect_inverter(host, port, family, timeout, dtls)
        else:
            broadcast_host = broadcast_host or get_default_broadcast_host()
            inverter = await find_inverter(port, family, timeout, dtls, broadcast_host, discovery_port, discovery_timeout)
    except goodwe.exceptions.MaxRetriesException:
        handle_max_retries_exception()
        return
    except goodwe.exceptions.InverterError as error:
        handle_inverter_error(error)
        return
    except PermissionError:
        handle_permission_error()
        return

    if inverter is None:
        return

    print_inverter_info(inverter)
    await get_runtime_data(inverter)


def parse_args():
    parser = argparse.ArgumentParser(description="Read runtime data from a GoodWe inverter.")
    parser.add_argument("--host", help="Inverter IP address or hostname. Skips discovery when provided.")
    parser.add_argument("--port", type=int, default=8899, help="Inverter port to connect to. Use 502 for TCP/Modbus.")
    parser.add_argument("--family", default="ET", choices=("ET", "EH", "BT", "BH", "ES", "EM", "BP", "DT", "MS", "D-NS", "XS"), help="Inverter family hint.")
    parser.add_argument("--timeout", type=int, default=1, help="Seconds to wait for each inverter request before retrying.")
    parser.add_argument("--dtls", action="store_true", help="Use DTLS-encrypted local Modbus, required by some Kit-20 dongles.")
    parser.add_argument("--broadcast-host", help="Directed broadcast address for fallback discovery.")
    parser.add_argument("--discovery-port", type=int, default=48899, help="UDP discovery port for fallback discovery.")
    parser.add_argument("--discovery-timeout", type=float, default=1, help="Seconds to wait for directed UDP fallback discovery.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args.host, args.port, args.family, args.timeout, args.dtls, args.broadcast_host, args.discovery_port, args.discovery_timeout))
