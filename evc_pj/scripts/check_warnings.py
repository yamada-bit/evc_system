import os
import sys
import warnings
from pathlib import Path
from io import StringIO
from contextlib import redirect_stderr

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

import django
django.setup()

# 自作コードは厳格
warnings.filterwarnings(
    "error",
    category=DeprecationWarning,
    module=r"^config|^apps"
)

# 第三者ライブラリは除外
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module=r"httplib2.*"
)

stderr = StringIO()

try:
    with redirect_stderr(stderr):
        import django.core.checks
        django.core.checks.run_checks()
except DeprecationWarning as e:
    print("❌ 非推奨警告が検出されました:\n")
    print(e)
    sys.exit(1)

output = stderr.getvalue()

if output:
    print("⚠ 非推奨警告があります:\n")
    print(output)
    sys.exit(1)

print("✅ 非推奨警告は検出されませんでした")
sys.exit(0)
