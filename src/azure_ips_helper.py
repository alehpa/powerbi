import argparse
import requests
import re
import json
import ipaddress
import sys


JSON_KEY_REGEX = "(?<=href=['\"])https://download\.microsoft.com/download.+\.json"


def get_service_tag_file_download_url(root_url):
    headers = {"User-Agent": "My-user-agent"}

    response = requests.get(root_url, headers=headers)
    source = response.text
    match = re.search(JSON_KEY_REGEX, source)

    if not match:
        print("Can't find service tag file to download")
        sys.exit(2)

    json_url = match.group(0)
    service_tags_obj = requests.get(json_url).json()
    return service_tags_obj["values"]


def filter_regions(all_services, target_regions, prefix_of_region):
    return [
        region
        for region in all_services
        if region["name"].startswith(prefix_of_region)
        and (region["properties"]["region"] in target_regions)
    ]


def filter_services(all_services, target_services_name):
    return [
        service for service in all_services if service["name"] in target_services_name
    ]


def get_ip_networks(ip_list):
    return [ipaddress.IPv4Network(ip) for ip in ip_list if ":" not in ip]


def get_ips(target_regions, target_services, source_file_path=None) -> json:
    root_url = "https://www.microsoft.com/en-us/download/confirmation.aspx?id=56519"
    prefix_of_region = "AzureCloud."

    if source_file_path:
        with open(source_file_path, "r", encoding="utf-8") as json_file:
            service_tags_obj = json.load(json_file)
            all_services = service_tags_obj["values"]
    else:
        all_services = get_service_tag_file_download_url(root_url)

    target_regions = filter_regions(all_services, target_regions, prefix_of_region)
    target_services = filter_services(all_services, target_services)

    region_to_ip = {
        region["properties"]["region"]: get_ip_networks(
            region["properties"]["addressPrefixes"]
        )
        for region in target_regions
    }

    service_to_region = {}
    for service in target_services:
        ip4_row_list = get_ip_networks(service["properties"]["addressPrefixes"])
        service_to_region[service["name"]] = {}
        for region_name, ip4_networks in region_to_ip.items():
            filtered_subnets = [
                str(subnet)
                for subnet in ip4_row_list
                if any(
                    subnet.subnet_of(current_network)
                    for current_network in ip4_networks
                )
            ]
            service_to_region[service["name"]][region_name] = filtered_subnets

    print(service_to_region)


class CustomFormatter(argparse.HelpFormatter):
    def add_examples(self, examples):
        if examples:
            self._add_item(self._format_text("Examples:"))
            for example in examples:
                self._add_item(self._format_text(f"  {example}"))


if __name__ == "__main__":
    examples = [
        "python3 azure_ips_helper.py --target_regions northeurope northeurope2 --target_services PowerBI PowerQueryOnline",
        "python3 azure_ips_helper.py --target_regions westeurope --target_services PowerBI --source_file_path 'tests/testfiles/ServiceTags_Public_20230807.json'",
    ]

    parser = argparse.ArgumentParser(
        description="Retrieve Azure service IP ranges for specified regions and services.",
        formatter_class=lambda prog: CustomFormatter(prog, max_help_position=30),
        epilog="License: MIT",
    )

    parser.add_argument(
        "--target_regions",
        nargs="+",
        required=True,
        help="List of target regions to filter (e.g., northeurope northeurope2)",
    )
    parser.add_argument(
        "--target_services",
        nargs="+",
        required=True,
        help="List of target service names to filter (e.g., PowerBI PowerQueryOnline)",
    )

    parser.add_argument(
        "--source_file_path",
        nargs="?",
        required=False,
        help="Path to service tag file to read from",
    )

    args = parser.parse_args()

    get_ips(args.target_regions, args.target_services, args.source_file_path)
