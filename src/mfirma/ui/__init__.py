"""Interfaccia Qt di mFirma."""

__all__ = ["run_application", "run_qt_dashboard"]


def __getattr__(name: str):
    if name in __all__:
        from .application import run_application, run_qt_dashboard

        return {
            "run_application": run_application,
            "run_qt_dashboard": run_qt_dashboard,
        }[name]
    raise AttributeError(name)
