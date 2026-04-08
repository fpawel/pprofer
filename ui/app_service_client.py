import requests


def get_stack(base_url, func, line, inline):
    resp = requests.get(
        f"{base_url}/stack",
        params={
            "func": func,
            "line": line,
            "inline": inline,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_labels(base_url):
    resp = requests.get(
        f"{base_url}/labels",
        timeout=5,
    )
    resp.raise_for_status()

    data = resp.json()
    if not isinstance(data, list):
        return []

    return [str(x) for x in data if str(x).strip()]