"""
Exécution d'actions sur des applications Windows via pywinauto (cible
les éléments d'UI réels, pas des coordonnées pixel fixes).

Le ACTION_WHITELIST est le garde-fou anti-hallucination central :
le LLM ne peut JAMAIS déclencher une action qui n'y figure pas.
"""
from pywinauto import Application
from backend.security.panic_button import check_abort

ACTION_WHITELIST = {}


def register_action(name: str):
    def decorator(func):
        ACTION_WHITELIST[name] = func
        return func
    return decorator


def execute_action(name: str, **kwargs):
    check_abort()
    if name not in ACTION_WHITELIST:
        raise ValueError(f"Action '{name}' inconnue - exécution refusée.")
    return ACTION_WHITELIST[name](**kwargs)


@register_action("open_app_and_focus")
def open_app_and_focus(path: str):
    check_abort()
    app = Application(backend="uia").start(path)
    return app


@register_action("type_text_in_field")
def type_text_in_field(window_title: str, control_name: str, text: str):
    check_abort()
    app = Application(backend="uia").connect(title_re=window_title)
    win = app.window(title_re=window_title)
    win[control_name].type_keys(text, with_spaces=True)
