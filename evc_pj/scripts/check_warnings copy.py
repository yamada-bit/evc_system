# ruff: noqa: E402
import os
import sys
import warnings
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

import django

django.setup()

def main():
    buffer = StringIO()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("default")
        # 自分のコードは厳格に
        warnings.filterwarnings(
            "error",
            category=DeprecationWarning,
            module=r"^config|^apps"
        )

        # 外部ライブラリは抑制
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            module=r"httplib2.*"
        )

        # Django 内部チェック
        from django.core.management import call_command
        with redirect_stderr(buffer):
            call_command("check")

    # 対象とする警告
    target = [
        w for w in caught
        if issubclass(w.category, (DeprecationWarning,))
    ]

    if target:
        print("❌ 非推奨警告が検出されました:\n")
        for w in target:
            print(f"- {w.category.__name__}: {w.message}")
            print(f"  file: {w.filename}:{w.lineno}\n")

        sys.exit(1)

    print("✅ 非推奨警告は検出されませんでした")
    sys.exit(0)

if __name__ == "__main__":
    main()
