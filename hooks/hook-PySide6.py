# PyInstaller hook for PySide6
# This hook ensures all PySide6 modules are properly collected


def hook(hook_api):
    import PySide6

    qt_modules = PySide6._find_all_qt_modules()

    # Add PySide6.<module> imports
    for module in qt_modules:
        hook_api.add_imports(f"PySide6.{module}")

    # Add shiboken6 imports
    try:
        import shiboken6

        hook_api.add_imports("shiboken6")
    except ImportError:
        pass
