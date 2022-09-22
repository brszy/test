from copy import deepcopy
from collections import defaultdict
import textwrap
import os
from prettytable import PrettyTable
import csv
from nornir.core import Nornir
from nornir.core.task import AggregatedResult

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




def print_table(
    result,
    expand_field=None,
    headers=None,
    nornir=None,
    resolve_fields=None,
    max_width=40,
    format="pretty",
    save_csv=False,
    name=None,
    path=None,
    sep=",",
):
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
            for row in expanded_records:
                for r in row:
                    r["@host"] = host
            records.extend(expanded_records)
        if (
            not headers
        ):  
            headers = set()
            for r in records:
                for rec in r:
                    headers |= set(rec.keys())
        headers = sorted(headers)
        data_table.field_names = headers
        for r in records:
            for rec in r:
                row = normalize_row(headers, rec)
                if format == "pretty":
                    row = [textwrap.fill(str(field), width=max_width) for field in row]
                data_table.add_row(row)
        if format == "pretty":
            print(data_table)
        elif format == "csv":
            if save_csv==True:
                final_path=f"{path}/compare/{name}.csv"
                with open(final_path, 'w+', newline='') as f:
                    f.write(data_table.get_csv_string())
            else:
                print(sep.join(headers))
                for row in data_table._rows:
                    print(sep.join([str(field) for field in row]))
        else:
            print(f"Unknown format: {format}")


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
