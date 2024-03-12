# Sunpower Stats

Reading Sunpower stats and putting them into Influx

## Config and such

Followed some blog posts. Gruby's post below has an HAProxy config that you can run on an RPi plugged in to the management port to proxy requests to the RPi (on your network) to the PVS system.

* [Gruby, Scott (2020 April 28). Monitoring a SunPower Solar System.](https://blog.gruby.com/2020/04/28/monitoring-a-sunpower-solar-system/)
* [Durrett, Brett (2023 March 20). Getting Administrator Access to SunPower PVS6 with no Ethernet Port.](https://brett.durrett.net/getting-administrator-access-to-sunpower-pvs6-with-no-ethernet-port/)


## Getting data from the management port

Making a request to the device at `http://<hostname>/cgi-bin/dl_cgi?Command=DeviceList` will return a JSON with the devices listed.

```
import requests

resp = requests.get(
    url="http://172.22.22.33/cgi-bin/dl_cgi",
    params={"Command": "DeviceList"},
)
devices = {}
for dev in resp.json()["devices"]:
    devices.setdefault(dev["DEVICE_TYPE"], []).append(dev)
```

## Devices

There are three `DEVICE_TYPE`'s:
```
>>> list(devices.keys())
['PVS', 'Power Meter', 'Inverter']
```

In my case, there's 1 PVS (Photovoltaic System?), 2 Power Meters (one for generation, one for consumption?), and each panel has an inverter.

### PVS

```
[{'DETAIL': 'detail',
  'STATE': 'working',
  'STATEDESCR': 'Working',
  'SERIAL': 'ZT230123456789F0123',
  'MODEL': 'PV Supervisor PVS6',
  'HWVER': '6.03',
  'SWVER': '2023.8, Build 61550',
  'DEVICE_TYPE': 'PVS',
  'DATATIME': '2024,03,11,23,15,00',
  'dl_err_count': '0',
  'dl_comm_err': '430',
  'dl_skipped_scans': '0',
  'dl_scan_time': '1',
  'dl_untransmitted': '513587',
  'dl_uptime': '120405',
  'dl_cpu_load': '0.54',
  'dl_mem_used': '80296',
  'dl_flash_avail': '72395',
  'panid': 1280133860,
  'CURTIME': '2024,03,11,23,19,00'}]
```

### Power Meter

One has the subtype `GROSS_PRODUCTION_SITE`, while the other is `NET_CONSUMPTION_LOADSIDE`.

```
{'ISDETAIL': True,
 'SERIAL': 'PVS6M23012345p',
 'TYPE': 'PVS5-METER-P',
 'STATE': 'working',
 'STATEDESCR': 'Working',
 'MODEL': 'PVS6M0400p',
 'DESCR': 'Power Meter PVS6M23012345p',
 'DEVICE_TYPE': 'Power Meter',
 'interface': 'mime',
 'production_subtype_enum': 'GROSS_PRODUCTION_SITE',
 'subtype': 'GROSS_PRODUCTION_SITE',
 'SWVER': '3000',
 'PORT': '',
 'DATATIME': '2024,03,11,23,19,00',
 'ct_scl_fctr': '50',
 'net_ltea_3phsum_kwh': '2202.9',
 'p_3phsum_kw': '0.6804',
 'q_3phsum_kvar': '0.5557',
 's_3phsum_kva': '0.8947',
 'tot_pf_rto': '0.7233',
 'freq_hz': '60',
 'i_a': '3.6434',
 'v12_v': '245.5848',
 'CAL0': '50',
 'origin': 'data_logger',
 'OPERATION': 'noop',
 'CURTIME': '2024,03,11,23,19,01'}
```

### Inverter

At night, the

```
{'ISDETAIL': True,
 'SERIAL': 'E00122334455667',
 'TYPE': 'SOLARBRIDGE',
 'STATE': 'working',
 'STATEDESCR': 'Working',
 'MODEL': 'AC_Module_Type_H',
 'DESCR': 'Inverter E00122334455667',
 'DEVICE_TYPE': 'Inverter',
 'hw_version': '4407',
 'interface': 'mime',
 'module_serial': '',
 'PANEL': 'WAAREE-WSMDi-400W',
 'slave': 0,
 'SWVER': '4.21.4',
 'PORT': '',
 'MOD_SN': '',
 'NMPLT_SKU': '',
 'DATATIME': '2024,03,11,23,18,42',
 'ltea_3phsum_kwh': '89.4825',
 'p_3phsum_kw': '0.0301',
 'vln_3phavg_v': '244.79',
 'i_3phsum_a': '0.12',
 'p_mppt1_kw': '0.0305',
 'v_mppt1_v': '36.7',
 'i_mppt1_a': '0.83',
 't_htsnk_degc': '23',
 'freq_hz': '60',
 'stat_ind': '0',
 'origin': 'data_logger',
 'OPERATION': 'noop',
 'CURTIME': '2024,03,11,23,19,01'}
```
