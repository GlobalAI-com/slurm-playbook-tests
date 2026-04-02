import ipaddress
import os
import sys
import requests

# Set the environment variables NETBOX_URL and NETBOX_TOKEN
# export NETBOX_URL='http://netbox.ssvc.nyc1.globalai.run:8088'
# export NETBOX_TOKEN='nbt_...'
NETBOX_URL = os.environ["NETBOX_URL"].rstrip("/")
NETBOX_TOKEN = os.environ["NETBOX_TOKEN"]  # include Bearer prefix if your NetBox token requires it
PREFIXLEN = 24

# Will increment by 1 for each device
START_IP = "10.3.10.39"

# Put the devices here in the exact order you want IPs assigned
DEVICE_NAMES = [
    "im-gb300-r02-c001",
    "im-gb300-r02-c002",
    "im-gb300-r02-c003",
    "im-gb300-r02-c004",
    "im-gb300-r02-c005",
    "im-gb300-r02-c006",
    "im-gb300-r02-c007",
    "im-gb300-r02-c008",
    "im-gb300-r02-c009",
    "im-gb300-r02-c010",
    "im-gb300-r02-c011",
    "im-gb300-r02-c012",
    "im-gb300-r02-c013",
    "im-gb300-r02-c014",
    "im-gb300-r02-c015",
    "im-gb300-r02-c016",
    "im-gb300-r02-c017",
    "im-gb300-r02-c018",
]

SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {NETBOX_TOKEN}" if not NETBOX_TOKEN.startswith("Bearer ") else NETBOX_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
})

def nb_get(path, params=None):
    r = SESSION.get(f"{NETBOX_URL}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def nb_post(path, payload):
    r = SESSION.post(f"{NETBOX_URL}{path}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def nb_patch(path, payload):
    r = SESSION.patch(f"{NETBOX_URL}{path}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def get_single(result, what):
    count = result.get("count", 0)
    if count != 1:
        raise RuntimeError(f"Expected 1 {what}, got {count}: {result}")
    return result["results"][0]

def main():
    base_ip = ipaddress.ip_address(START_IP)

    for idx, device_name in enumerate(DEVICE_NAMES):
        ip_obj = ipaddress.ip_address(int(base_ip) + idx)
        cidr = f"{ip_obj}/{PREFIXLEN}"

        # Find device
        device = get_single(
            nb_get("/api/dcim/devices/", params={"name": device_name}),
            f"device named {device_name}",
        )
        device_id = device["id"]

        # Find eth0 on that device
        iface = get_single(
            nb_get("/api/dcim/interfaces/", params={"device_id": device_id, "name": "eth0"}),
            f"eth0 for device {device_name}",
        )
        iface_id = iface["id"]

        # Create IP assigned to eth0
        payload = {
            "address": cidr,
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": iface_id,
            "status": "active",
        }
        ip_rec = nb_post("/api/ipam/ip-addresses/", payload)
        ip_id = ip_rec["id"]

        # Set primary IPv4 on device
        # In current NetBox APIs this field is typically primary_ip4.
        nb_patch(f"/api/dcim/devices/{device_id}/", {"primary_ip4": ip_id})

        print(f"{device_name}: assigned {cidr} to eth0 and set primary_ip4")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)