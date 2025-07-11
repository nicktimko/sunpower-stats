import argparse
import datetime
import json
import socket
import subprocess
import sys
import typing

import requests

import influx

# For a given DEVICE TYPE:
# * what are the measurements to grab from it, and what converter to use?
# * what are the additional tags to include?
DEVICE_LOG_SPEC = [
    {
        "device_pattern": {
            "DEVICE_TYPE": "PVS",
        },
        "name": "supervisor",
        "measurements": [
            ("dl_err_count", int),
            ("dl_comm_err", int),
            ("dl_skipped_scans", int),
            ("dl_scan_time", float),
            ("dl_untransmitted", int),
            ("dl_uptime", float),
            ("dl_cpu_load", float),
            ("dl_mem_used", int),
            ("dl_flash_avail", int),
        ],
        "tags": ["SERIAL"],
    },
    {
        "device_pattern": {
            "DEVICE_TYPE": "Power Meter",
            "subtype": "GROSS_PRODUCTION_SITE",
        },
        "name": "meter_production",
        "measurements": [
            ("ct_scl_fctr", float),  # '50',
            (
                "net_ltea_3phsum_kwh",
                float,
            ),  # '2206.66', cf. "neg_ltea_3phsum_kwh", "pos_ltea_3phsum_kwh"
            ("p_3phsum_kw", float),  # '3.0426',
            ("q_3phsum_kvar", float),  # '0.6076',
            ("s_3phsum_kva", float),  # '3.1163',
            ("tot_pf_rto", float),  # '0.9765',
            ("freq_hz", float),  # '60',
            ("i_a", float),  # '12.5379',  cf. "i1_a", "i2_a"
            ("v12_v", float),  # '248.55', cf. "v1n_v", "v2n_v", "v12_v"
            ("CAL0", float),  # '50',
            # no equiv for "p1_kw", "p2_kw"?
        ],
        "tags": [
            "SERIAL",
            "subtype",
        ],
    },
    {
        "device_pattern": {
            "DEVICE_TYPE": "Power Meter",
            "subtype": "NET_CONSUMPTION_LOADSIDE",
        },
        "name": "meter_consumption",
        "measurements": [
            ("ct_scl_fctr", float),  # '100',
            ("net_ltea_3phsum_kwh", float),  # '2194.12',
            ("p_3phsum_kw", float),  # '-3.7339',
            ("q_3phsum_kvar", float),  # '-0.7258',
            ("s_3phsum_kva", float),  # '3.8117',
            ("tot_pf_rto", float),  # '-0.9734',
            ("freq_hz", float),  # '60',
            ("i1_a", float),  # '15.2739',
            ("i2_a", float),  # '15.3827',
            ("v1n_v", float),  # '124.2079',
            ("v2n_v", float),  # '124.4629',
            ("v12_v", float),  # '248.6707',
            ("p1_kw", float),  # '-1.882',
            ("p2_kw", float),  # '-1.8519',
            ("neg_ltea_3phsum_kwh", float),  # '1537.46',
            ("pos_ltea_3phsum_kwh", float),  # '3731.6',
            ("CAL0", int),  # 100, 50  - calibration? unsure...log it.
        ],
        "tags": [
            "SERIAL",
            "subtype",
        ],
    },
    {
        "device_pattern": {
            "DEVICE_TYPE": "Inverter",
        },
        "name": "inverter",
        "measurements": [
            ("ltea_3phsum_kwh", float),  # '89.4825',
            ("p_3phsum_kw", float),  # '0.0301',
            ("vln_3phavg_v", float),  # '244.79',
            ("i_3phsum_a", float),  # '0.12',
            ("p_mppt1_kw", float),  # '0.0305',
            ("v_mppt1_v", float),  # '36.7',
            ("i_mppt1_a", float),  # '0.83',
            ("t_htsnk_degc", float),  # '23',
            ("freq_hz", float),  # '60',
            ("stat_ind", float),  # '0',
        ],
        "tags": [
            "SERIAL",
        ],
    },
]


def digest_device_data(data):
    devices = {}
    for dev in data["devices"]:
        devices.setdefault(dev["DEVICE_TYPE"], [])
        devices[dev["DEVICE_TYPE"]].append(dev)

    devices["PVS"]


def solar_devicelist(
    base_url,
) -> typing.Dict[str, typing.Union[str, typing.List[typing.Dict[str, str]]]]:
    """
    Takes ~5-6 seconds, about 1/5 sec per device to list.
    """
    resp = requests.get(
        url=f"{base_url}/cgi-bin/dl_cgi",
        params={"Command": "DeviceList"},
    )
    resp.raise_for_status()
    return resp.json()


def solar_devicedetails(base_url, serial):
    """
    Alledgedly this is a command, but doesn't work on my PVS5. Just returns
    {"result": "unknown command"}

    https://github.com/ginoledesma/sunpower-pvs-exporter/blob/master/sunpower_pvs_notes.md
    """
    resp = requests.get(
        url=f"{base_url}/cgi-bin/dl_cgi",
        params={"Command": "DeviceDetails", "SerialNumber": serial},
    )
    # resp.raise_for_status()
    # return resp.json()
    return resp, resp.json()


def commatime_convert(time: str) -> datetime.datetime:
    """
    Timestamps returned are in the format 'YYYY,mm,dd,HH,MM,SS' in UTC time
    """
    return datetime.datetime(
        *(int(x) for x in time.split(",")),
        tzinfo=datetime.timezone.utc,
    )


def commatime_convert_ns(time: str) -> int:
    return int(commatime_convert(time).timestamp()) * 1_000_000_000


def parse_devices(
    devices: typing.List[typing.Dict[str, str]]
) -> typing.List[influx.Point]:
    points: list[influx.Point] = []
    for device in devices:
        for spec in DEVICE_LOG_SPEC:
            if not all(device.get(k) == v for k, v in spec["device_pattern"].items()):
                continue
            point = influx.Point(
                measurement=spec["name"],
                fields={fld: conv(device[fld]) for fld, conv in spec["measurements"]},
                tags={t: str(device[t]) for t in spec["tags"]},
                time=commatime_convert_ns(device["DATATIME"]),
            )
            points.append(point)
    return points


### COMMANDS


def debug_timestamps(
    solar_base_url: str, influx_client: influx.Client, more_args: typing.List[str]
):
    """Examining how often the timestamps update"""
    data = solar_devicelist(solar_base_url)
    for dev in data["devices"]:
        print(
            "{:20s} {} {}".format(
                dev["SERIAL"],
                commatime_convert(dev["CURTIME"]).isoformat(),
                commatime_convert(dev["DATATIME"]).isoformat(),
            )
        )
    return 0


def device_details(
    solar_base_url: str, influx_client: influx.Client, more_args: typing.List[str]
):
    # DOES NOT WORK
    try:
        (serial,) = more_args
    except ValueError:
        print("provide one additional argument: the serial number", file=sys.stderr)
        return 1

    print(solar_devicedetails(solar_base_url, serial))


def print_lines(
    solar_base_url: str, influx_client: influx.Client, more_args: typing.List[str]
):
    data = solar_devicelist(solar_base_url)
    points = parse_devices(data["devices"])
    for point in points:
        print(point.as_line(), end="")


def record_stats(
    solar_base_url: str, influx_client: influx.Client, more_args: typing.List[str]
):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print out stat lines"
    )
    args = parser.parse_args(more_args)

    if args.verbose:
        print("making request...")

    data = solar_devicelist(solar_base_url)
    points = parse_devices(data["devices"])

    if args.verbose:
        print(datetime.datetime.utcnow().isoformat())
        for point in points:
            print(point.as_line(), end="")

    print(influx_client.write_points(points))


MODES = {
    "debug-timestamps": debug_timestamps,
    "device-details": device_details,
    "print-lines": print_lines,
    "record-stats": record_stats,
}


def find_gateway(interface: str) -> str:
    """
    Get the gateway for a given interface.
    """
    result = subprocess.check_output(
        "ip route show 0.0.0.0/0 dev".split() + [interface],
        universal_newlines=True,
    )
    return result.split()[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("-c", "--config", default="solarstatconf.json")
    # parser.add_argument(
    #     "-H", "--host-for-stats",
    #     help="Hostname to query for stats. Will attempt to autodetect if not provided."
    # )
    # parser.add_argument(
    #     "-i", "--interface",
    #     default="eth0",
    #     help="Interface to look for the stats server on",
    # )
    args, more_args = parser.parse_known_args()

    with open(args.config) as f:
        conf = json.load(f)

    influx_client = influx.Client(**conf["influx"])

    addr_info = socket.getaddrinfo("www.sunpowerconsole.com", None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    resolved_ip = addr_info[0][4][0]
    solar_base_url = "http://" + resolved_ip

    # if args.host_for_stats:
    #     solar_base_url = "http://" + args.host_for_stats
    # else:
    #     try:
    #         solar_base_url = conf["solar_base_url"]
    #     except KeyError:
    #         solar_base_url = "http://" + find_gateway(args.interface)

    return MODES[args.mode](solar_base_url, influx_client, more_args)


if __name__ == "__main__":
    sys.exit(main())
