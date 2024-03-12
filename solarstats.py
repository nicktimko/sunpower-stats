import argparse
import datetime
import json
import sys

import requests

import influx

# For a given DEVICE TYPE:
# * what are the measurements to grab from it, and what converter to use?
# * what are the additional tags to include?
relevant_fields = {
    "PVS": {
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
        "tags": [],
    },
    "Power Meter": {
        "measurements": [
            ("ct_scl_fctr", float), # '100',
            ("net_ltea_3phsum_kwh", float), # '2194.12',
            ("p_3phsum_kw", float), # '-3.7339',
            ("q_3phsum_kvar", float), # '-0.7258',
            ("s_3phsum_kva", float), # '3.8117',
            ("tot_pf_rto", float), # '-0.9734',
            ("freq_hz", float), # '60',
            ("i1_a", float), # '15.2739',
            ("i2_a", float), # '15.3827',
            ("v1n_v", float), # '124.2079',
            ("v2n_v", float), # '124.4629',
            ("v12_v", float), # '248.6707',
            ("p1_kw", float), # '-1.882',
            ("p2_kw", float), # '-1.8519',
            ("neg_ltea_3phsum_kwh", float), # '1537.46',
            ("pos_ltea_3phsum_kwh", float), # '3731.6',
            ("CAL0", int), # 100, 50  - calibration? unsure...log it.
        ],
        "tags": [
            "SERIAL",
            "subtype",
        ],
    },
    "Inverter": {
        "measurements": [
            ("ltea_3phsum_kwh", float), # '89.4825',
            ("p_3phsum_kw", float), # '0.0301',
            ("vln_3phavg_v", float), # '244.79',
            ("i_3phsum_a", float), # '0.12',
            ("p_mppt1_kw", float), # '0.0305',
            ("v_mppt1_v", float), # '36.7',
            ("i_mppt1_a", float), # '0.83',
            ("t_htsnk_degc", float), # '23',
            ("freq_hz", float), # '60',
            ("stat_ind", float), # '0',
        ],
        "tags": [
            "SERIAL",
        ],
    },
}

def digest_device_data(data):
    devices = {}
    for dev in data["devices"]:
        devices.setdefault(dev["DEVICE_TYPE"], [])
        devices[dev["DEVICE_TYPE"]].append(dev)

    devices["PVS"]


def solar_devicelist(base_url):
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
    return resp.json()


def commatime_convert(time) -> datetime.datetime:
    """
    Timestamps returned are in the format 'YYYY,mm,dd,HH,MM,SS' in UTC time
    """
    return datetime.datetime(
        *(int(x) for x in time.split(",")),
        tzinfo=datetime.timezone.utc,
    )


def debug_timestamps(solar_base_url, influx_client, more_args):
    """Examining how often the timestamps update"""
    data = solar_devicelist(solar_base_url)
    for dev in data["devices"]:
        print("{:20s} {} {}".format(
            dev["SERIAL"],
            commatime_convert(dev["CURTIME"]).isoformat(),
            commatime_convert(dev["DATATIME"]).isoformat(),
        ))
    return 0


def device_details(solar_base_url, influx_client, more_args):
    try:
        (serial,) = more_args
    except ValueError:
        print("provide one additional argument: the serial number", file=sys.stderr)
        return 1

    print(solar_devicedetails(solar_base_url, serial))


MODES = {
    "debug-timestamps": debug_timestamps,
    "device-details": device_details,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("-c", "--config", default="solarstatconf.json")
    args, more_args = parser.parse_known_args()

    with open(args.config) as f:
        conf = json.load(f)

    influx_client = influx.Client(**conf["influx"])

    return MODES[args.mode](conf["solar_base_url"], influx_client, more_args)



if __name__ == "__main__":
    sys.exit(main())
