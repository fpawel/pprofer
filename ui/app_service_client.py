import requests


def get_stack(base_url, func, line, inline):
    """Запрашивает stack trace для выбранной серии."""
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
    """Запрашивает человекочитаемые labels, которые backend вычислил для профиля."""
    resp = requests.get(
        f"{base_url}/labels",
        timeout=5,
    )
    resp.raise_for_status()

    data = resp.json()
    if not isinstance(data, list):
        return []

    # Приводим всё к строкам и выкидываем пустые значения,
    # чтобы UI не показывал мусор вида "", None и т.п.
    return [str(x) for x in data if str(x).strip()]
