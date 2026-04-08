import requests


def _get_requester(session=None):
    """
    Возвращает объект с методом .get(...).

    Если передан requests.Session, используем его:
    это позволяет потоку закрыть сессию из stop() и аккуратно прервать запрос.
    """
    return session if session is not None else requests


def get_stack(base_url, func, line, inline, session=None, timeout=(3, 10)):
    """Запрашивает stack trace для выбранной серии."""
    requester = _get_requester(session)

    resp = requester.get(
        f"{base_url}/stack",
        params={
            "func": func,
            "line": line,
            "inline": inline,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def get_labels(base_url, session=None, timeout=(3, 5)):
    """Запрашивает человекочитаемые labels, которые backend вычислил для профиля."""
    requester = _get_requester(session)

    resp = requester.get(
        f"{base_url}/labels",
        timeout=timeout,
    )
    resp.raise_for_status()

    data = resp.json()
    if not isinstance(data, list):
        return []

    # Приводим всё к строкам и выкидываем пустые значения,
    # чтобы UI не показывал мусор вида "", None и т.п.
    return [str(x) for x in data if str(x).strip()]
