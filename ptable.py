from copy import deepcopy
from collections import defaultdict
import textwrap

from prettytable import PrettyTable

from nornir.core import Nornir
from nornir.core.task import AggregatedResult
from nornir.plugins.functions.inv import resolve_ip

MAX_MULTI_RESULTS = 10


def expand_row(data, field=None):
    rows = []
    if field in data:
        if (
            isinstance(data[field], list)
            and len(data[field])
            and isinstance(data[field][0], dict)
        ):
            for rec in data[field]:
                record = {k: v for k, v in data.items() if k != field}
                rec = {"~" + k: v for k, v in rec.items()}
                record.update(rec)
                rows.append(record)
        elif isinstance(data[field], dict):
            record = {k: v for k, v in data.items() if k != field}
            rec = {"~" + k: v for k, v in data[field]}
            record.update(data[field])
            rows.append(record)
        else:
            rows.append(deepcopy(data))
    else:
        rows.append(deepcopy(data))
    return rows


def print_status(nornir, result):
    """
    Prints a summary of the result status aggregated by status

    Arguments:
        nornir (:obj:`nornir.core.Nornir`): Nornir object used to generate result
        result (:obj:`nornir.core.task.Result`): Result object from a previous nornir-run

    """
    if isinstance(nornir, Nornir):
        inv_hosts = list(nornir.inventory.hosts.keys())
    else:
        raise ValueError("nornir parameter must be of type 'Nornir'")
    if isinstance(result, AggregatedResult):
        status_data = defaultdict(dict)
        for host, host_data in result.items():
            try:
                _ = getattr(host_data[0], "response")
            except AttributeError:
                continue
            for response in host_data[0].response:
                if response.status_code == 200:
                    if len(host_data[0].result):
                        if host_data[0].result.get("items"):
                            if len(host_data[0].result["items"]):
                                status = "OK"
                            else:
                                status = "OK(empty)"
                        else:
                            status = "OK"
                    else:
                        status = "OK(empty)"
                elif 400 <= response.status_code <= 499:
                    if response.status_code == 401:
                        status_str = "AUTH_ERR"
                    elif response.status_code == 408:
                        status_str = "TIMEOUT"
                    else:
                        status_str = "NOTFOUND"
                    status = f"{status_str}({response.status_code})"
                else:
                    status = f"SERVER_ERROR({response.status_code})"
                if status not in status_data:
                    status_data[status] = set()
                status_data[status].add(host)
            try:
                inv_hosts.remove(host)
            except ValueError:
                raise ValueError(
                    "Host {} in result is not in specified inventory. Result probably generated with different nornir-object".format(
                        host
                    )
                )
    for status, hosts in status_data.items():
        print("{:<15}:{}".format(status, " ".join(hosts)))
    if len(inv_hosts):
        print("{:<15}:{}".format("NO REPONSE", " ".join(inv_hosts)))


def print_table(
    result,
    expand_field=None,
    headers=None,
    nornir=None,
    resolve_fields=None,
    max_width=40,
    format="pretty",
    sep=",",
):
    """
    Prints the :obj:`nornir.core.task.Result` from a previous task to screen

    Arguments:
        result (:obj:`nornir.core.task.Result`): from a previous task
        expand_field (str): name of composite field that will be expanded, e.g. 'neighbors' in bgp resource
        headers (list): a list of headers to display. If None, headers will be derived from result
        nornir (:obj:`nornir.core.Nornir`): optional nornir object. Only required for 'resolve_fields' to have effect
        resolve_fields (list): list of fields containing an IP address that will be attempted to be resolved to a hostname
            this requires the inventory to be populated with interface IP-addresses, e.g. using populate_ip()
            the 'nornir' parameter is required to allow access to the inventory instance
        max_width: max width of a table column
        format (str): format of the output. Default 'pretty'. Other options: 'csv'
        sep (str): separator for csv-format

    """
    # import pdb; pdb.set_trace()
    if isinstance(result, AggregatedResult):
        data_table = PrettyTable()
        records = []
        title = ""
        for host, host_data in result.items():
            if not title:
                title = f"{result.name}:{host_data[0].name} ({expand_field} expanded)"
            if not isinstance(host_data[0].result, (list, dict)):
                continue
            if not len(host_data[0].result):
                continue
            expanded_records = []
            if "__count" in host_data[0].result:
                for data in host_data[0].result.get("items"):
                    expanded_records.extend(expand_row(data, expand_field))
            else:
                expanded_records = expand_row(host_data[0].result, expand_field)
            for r in expanded_records:
                r["@host"] = host
            records.extend(expanded_records)
        if (
            not headers
        ):  # if not headers specified in param-list, generate a superset of attribs as queries to different node-types may yield different attribs
            headers = set()
            for rec in records:
                headers |= set(rec.keys())
        headers = sorted(headers)
        data_table.field_names = headers
        for rec in records:
            row = normalize_row(headers, rec)
            if nornir:
                for resolve_field in resolve_fields:
                    try:
                        i = headers.index(resolve_field)
                    except ValueError:
                        continue
                    if row[i]:
                        row[i] += f"({resolve_ip(nornir, row[i])})"
            if format == "pretty":
                row = [textwrap.fill(str(field), width=max_width) for field in row]
            data_table.add_row(row)
        print(f"** {title} **")
        if format == "pretty":
            print(data_table)
        elif format == "csv":
            print(sep.join(headers))
            for row in data_table._rows:
                print(sep.join([str(field) for field in row]))
        else:
            print(f"Unknown format: {format}")
        print(f"Entries: {len(records)}")


def normalize_row(headers, data):
    row = []
    for h in headers:
        value = data.get(h)
        if isinstance(value, list):
            if len(value):
                if isinstance(value[0], (str, int, float)):
                    row.append(" ".join([str(e) for e in value]))
                else:
                    row.append(f"list of {h}")
            else:
                row.append("")
        elif isinstance(value, dict):
            row.append(f"h object")
        else:
            row.append(value)
    return row
