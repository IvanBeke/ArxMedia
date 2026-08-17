"""Django settings package for arxmedia."""

from importlib import import_module

_SETTINGS_MODULES = [
    'base',
    'security',
    'django_core',
    'database',
    'static_media',
    'api',
    'integrations',
    'celery',
    'logging_conf',
]

for _module_name in _SETTINGS_MODULES:
    _module = import_module(f'{__name__}.{_module_name}')
    for _setting_name in dir(_module):
        if _setting_name.isupper():
            globals()[_setting_name] = getattr(_module, _setting_name)

__all__ = [name for name in globals() if name.isupper()]
