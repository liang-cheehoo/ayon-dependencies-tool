#!/usr/bin/env python3
"""Upload a locally-built dependency package to an AYON server.

Usage:
    python upload_dep_package.py <zip_file> \
        --server https://ayon-dev.spuree.com \
        --api-key YOUR_API_KEY \
        --bundle BUNDLE_NAME
"""

import argparse
import json
import os
import sys

import requests


def main():
    parser = argparse.ArgumentParser(
        description="Upload a dependency package to AYON server"
    )
    parser.add_argument("zip_file", help="Path to the .zip dependency package")
    parser.add_argument("--server", required=True, help="AYON server URL")
    parser.add_argument("--api-key", required=True, help="AYON admin API key")
    parser.add_argument(
        "--bundle",
        help="Bundle name to assign the package to (reads from .json metadata if omitted)",
    )
    args = parser.parse_args()

    zip_path = args.zip_file
    json_path = zip_path + ".json"

    if not os.path.isfile(zip_path):
        print(f"Error: zip file not found: {zip_path}")
        sys.exit(1)

    if not os.path.isfile(json_path):
        print(f"Error: metadata file not found: {json_path}")
        sys.exit(1)

    with open(json_path) as f:
        metadata = json.load(f)

    server = args.server.rstrip("/")
    headers = {"Authorization": f"apiKey {args.api_key}"}
    filename = metadata["filename"]
    bundle_name = args.bundle or metadata.get("bundle_name")

    # Step 1: Register the dependency package
    print(f"Registering package '{filename}' on {server}...")
    register_payload = {
        "filename": filename,
        "platform": metadata["platform"],
        "size": metadata["size"],
        "checksum": metadata["checksum"],
        "checksumAlgorithm": metadata["checksum_algorithm"],
        "pythonModules": metadata["python_modules"],
        "sourceAddons": metadata["source_addons"],
        "installerVersion": metadata["installer_version"],
    }
    resp = requests.post(
        f"{server}/api/desktop/dependencyPackages",
        headers={**headers, "Content-Type": "application/json"},
        json=register_payload,
    )
    if resp.status_code == 409:
        print(f"Package '{filename}' already registered, skipping registration.")
    elif not resp.ok:
        print(f"Failed to register package: {resp.status_code} {resp.text}")
        sys.exit(1)
    else:
        print("Registered.")

    # Step 2: Upload the zip file
    file_size = os.path.getsize(zip_path)
    print(f"Uploading {filename} ({file_size / 1024 / 1024:.1f} MB)...")
    with open(zip_path, "rb") as f:
        resp = requests.put(
            f"{server}/api/desktop/dependencyPackages/{filename}",
            headers={**headers, "Content-Type": "application/octet-stream"},
            data=f,
        )
    if not resp.ok:
        print(f"Failed to upload: {resp.status_code} {resp.text}")
        sys.exit(1)
    print("Uploaded.")

    # Step 3: Assign to bundle
    if bundle_name:
        print(f"Assigning package to bundle '{bundle_name}'...")
        # Get current bundle config
        resp = requests.get(f"{server}/api/bundles", headers=headers)
        if not resp.ok:
            print(f"Failed to get bundles: {resp.status_code} {resp.text}")
            sys.exit(1)

        bundle = None
        for b in resp.json()["bundles"]:
            if b["name"] == bundle_name:
                bundle = b
                break

        if not bundle:
            print(f"Warning: bundle '{bundle_name}' not found, skipping assignment.")
        else:
            dep_packages = bundle.get("dependencyPackages", {})
            dep_packages[metadata["platform"]] = filename
            resp = requests.patch(
                f"{server}/api/bundles/{bundle_name}",
                headers={**headers, "Content-Type": "application/json"},
                json={"dependencyPackages": dep_packages},
            )
            if not resp.ok:
                print(f"Failed to update bundle: {resp.status_code} {resp.text}")
                sys.exit(1)
            print(f"Bundle '{bundle_name}' updated with Windows package.")
    else:
        print("No bundle name specified — package uploaded but not assigned to a bundle.")

    print("Done!")


if __name__ == "__main__":
    main()
