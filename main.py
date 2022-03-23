import configparser
import json
from datetime import datetime, timedelta
import sqlite3
from os import path, mkdir, PathLike, getcwd, chdir, remove
from tkinter.messagebox import NO
from typing import List
from urllib.parse import urlparse

import msgpack
import requests


def bool_from_str(input_str: str) -> bool:
    return input_str.lower() == "true"


def cwd_or_mkdir(new_cwd: PathLike[str] | str):
    if getcwd() == new_cwd:
        return
    elif path.exists(new_cwd):
        chdir(new_cwd)
    else:
        mkdir(new_cwd)
        chdir(new_cwd)


def dl_raw(url: str):
    req = requests.get(url, allow_redirects=True)
    raw_file = path.basename(urlparse(url).path)

    with open(raw_file, "w") as fd:
        fd.write(req.content.decode("utf-8"))

    now = datetime.utcnow()
    with open("db_info.ini", "w") as fd:
        r_inf = configparser.ConfigParser()
        r_inf["refresh_info"] = {
            "last_refresh": now.isoformat(),
            "next_refresh": (now + timedelta(days=1)).isoformat(),
        }

        r_inf.write(fd)

    return now, now + timedelta(days=1)


def check_raw(url: str) -> (datetime, datetime, bool):
    if path.exists("db_info.ini"):
        r_inf = configparser.ConfigParser()
        r_inf.read("db_info.ini")
        n_rfr = datetime.fromisoformat(r_inf["refresh_info"]["next_refresh"])
        if datetime.utcnow() > n_rfr:
            r = dl_raw(url)
            return r[0], r[1], True
        else:
            return (datetime.fromisoformat(r_inf["refresh_info"]["last_refresh"]),
                    datetime.fromisoformat(r_inf["refresh_info"]["next_refresh"]), False)
    else:
        r = dl_raw(url)
        return r[0], r[1], True


def parse_vendors(vendors: List[List[str]]):
    vendor_list = []
    for vendor in vendors:
        vendor_ = {"devices": []}
        device = {}
        for i, line in enumerate(vendor):
            if not line.startswith("\t"):
                ls = line.split("  ")
                vendor_["vendor"] = int(ls[0], 16)
                vendor_["vendor_name"] = ls[1]
                name_split = ls[1].split(" (")
                print(name_split)
                if len(name_split) > 1:
                    vendor_["wrong_id"] = (name_split[1].lower() == "wrong id)")
                    vendor_["clean_name"] = name_split[0]
                else:
                    vendor_["wrong_id"] = False
                    vendor_["clean_name"] = None
            elif line.startswith("\t") and not line.startswith("\t\t"):
                if device:
                    vendor_["devices"].append(device)
                ls = line.split("  ")
                ls[0] = ls[0].replace("\t", "")
                device = {
                    "device": int(ls[0], 16),
                    "device_name": ls[1],
                    "sub_devices": [],
                }
            elif line.startswith("\t\t"):
                ls = line.split("  ")
                ls[0] = ls[0].replace("\t", "")
                code_split = ls[0].split(" ")
                sub_device = {
                    "subvendor": int(code_split[0], 16),
                    "subdevice": int(code_split[1], 16),
                    "subsystem_name": ls[1],
                }
                device["sub_devices"].append(sub_device)

        if device:
            vendor_["devices"].append(device)
        vendor_list.append(vendor_)

    return vendor_list


def parse_categories(classes: List[List[str]]):
    category_list = []
    for _class in classes:
        class_ = {"subclasses": []}
        subclass = {}
        for i, line in enumerate(_class):
            if not line.startswith("\t"):
                ls = line.split("  ")
                code_split = ls[0].split(" ")
                class_["class"] = int(code_split[1], 16)
                class_["class_name"] = ls[1]
            elif line.startswith("\t") and not line.startswith("\t\t"):
                if subclass:
                    class_["subclasses"].append(subclass)
                ls = line.split("  ")
                ls[0] = ls[0].replace("\t", "")
                subclass = {
                    "subclass": int(ls[0], 16),
                    "subclass_name": ls[1],
                    "prog_ifs": [],
                }
            elif line.startswith("\t\t"):
                ls = line.split("  ")
                ls[0] = ls[0].replace("\t", "")
                prog_if = {
                    "prog_if": int(ls[0], 16),
                    "prog_if_name": ls[1],
                }
                subclass["prog_ifs"].append(prog_if)

        if subclass:
            class_["subclasses"].append(subclass)
        category_list.append(class_)

    return category_list


def bake_to_sqlite(f_name, schema_file, devices, classes):
    if path.exists(f_name):
        remove(f_name)
    conn = sqlite3.connect(f_name)
    with open(f"../{schema_file}", "r") as fd:
        schema = fd.read()
    conn.executescript(schema)
    conn.commit()
    for vendor in devices:
        params = [vendor["vendor"], vendor["vendor_name"], vendor["clean_name"], vendor["wrong_id"]]
        conn.execute("INSERT INTO pci_vendor (vendor, name, clean_name, wrong_id) VALUES (:vendor, :vendor_name, :clean_name, :wrong_id);", params)
        for device in vendor["devices"]:
            params = [device["device"], vendor["vendor"], device["device_name"]]
            conn.execute("INSERT INTO pci_dev (device, vendor, name) VALUES (:device, :vendor_id, :name);", params)
            for subdevice in device["sub_devices"]:
                params = [device["device"], subdevice["subvendor"], subdevice["subdevice"], subdevice["subsystem_name"]]
                conn.execute("""
                INSERT INTO pci_sub_dev (parent_device, subvendor, subdevice, subsystem_name)
                VALUES (:parent_device, :subvendor, :subdevice, :subsystem_name);
                """, params)
    conn.commit()

    for class_ in classes:
        conn.execute("""
        INSERT INTO pci_class (class, class_name)
        VALUES (:class, :class_name);
        """, [class_["class"], class_["class_name"]])
        for subclass in class_["subclasses"]:
            conn.execute("""
                    INSERT INTO pci_subclass (parent_class, subclass, subclass_name)
                    VALUES (:parent_class, :subclass, :subclass_name);
                    """, [class_["class"], subclass["subclass"], subclass["subclass_name"]])
            for prog_if in subclass["prog_ifs"]:
                conn.execute("""
                INSERT INTO pci_prog_if(parent_subclass, prog_if, prog_if_name)
                VALUES (:parent_subclass, :prog_if, :prog_if_name);
                """, [subclass["subclass"], prog_if["prog_if"], prog_if["prog_if_name"]])
    conn.commit()

    conn.close()


def parse_db(contents: str):
    lines = contents.splitlines()
    vendors = []
    categories = []
    current_vendor = []
    current_category = []
    for i, l in enumerate(lines):
        if l.startswith("#") or not l:
            continue
        # If the line does not start with a tab or a C it's a vendor
        elif not l.startswith(("\t", "C")):
            if current_vendor:
                vendors.append(current_vendor)
            current_vendor = [l]
        elif l.startswith("C"):
            if current_vendor:
                vendors.append(current_vendor)
                current_vendor = []
            if current_category:
                categories.append(current_category)
            current_category = [l]
        elif l.startswith("\t"):
            if current_vendor:
                current_vendor.append(l)
            elif current_category:
                current_category.append(l)

    if current_category:
        categories.append(current_category)

    return parse_vendors(vendors), parse_categories(categories)


def main():
    cfg = configparser.ConfigParser(comment_prefixes=[";"])
    cfg.read("pcidb_baker.ini")

    raw_url = cfg["global"]["raw_db_url"]
    raw_file = path.basename(urlparse(raw_url).path)
    out_path = cfg["global"]["output_path"]
    work_path = cfg["global"]["work_path"]

    bake_matrix = {
        "msgpack": (bool_from_str(cfg["msgpack"]["bake"]), cfg["msgpack"]["output"]),
        "json": (bool_from_str(cfg["json"]["bake"]), cfg["json"]["output"]),
        "sqlite": (bool_from_str(cfg["sqlite"]["bake"]), cfg["sqlite"]["output"], cfg["sqlite"]["schema_file"]),
    }

    if not path.exists(out_path):
        mkdir(out_path)

    cwd_or_mkdir(work_path)
    print(f"Downloading the raw db from: {raw_url}")
    raw_info = check_raw(raw_url)
    if not raw_info[2]:
        print(f"Using cached version from {raw_info[0]}, to force re-download delete db_info.ini")
    else:
        print(f"Downloaded a new version valid until: {raw_info[1]}")

    with open(raw_file, "r") as rf:
        raw_c = rf.read()
        parsed = parse_db(raw_c)

    cwd_or_mkdir("..")
    cwd_or_mkdir(out_path)

    if bake_matrix["msgpack"][0]:
        structure = {
            "db_timestamp": raw_info[0].isoformat(),
            "vendors": parsed[0],
            "classes": parsed[1],
        }
        with open(bake_matrix["msgpack"][1], "wb") as fd:
            msgpack.dump(structure, fd)

    if bake_matrix["json"][0]:
        structure = {
            "db_timestamp": raw_info[0].isoformat(),
            "vendors": parsed[0],
            "classes": parsed[1],
        }
        with open(bake_matrix["json"][1], "w") as fd:
            json.dump(structure, fd)

    if bake_matrix["sqlite"][0]:
        bake_to_sqlite(bake_matrix["sqlite"][1], bake_matrix["sqlite"][2], parsed[0], parsed[1])


if __name__ == '__main__':
    main()
