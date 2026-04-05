import requests


def get_stack(base_url, profile, line, inline):
    return requests.get(
        f"{base_url}/stack",
        params={
            "profile": profile,
            "line": line,
            "inline": inline,
        },
    ).text