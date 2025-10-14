import importlib
import sys
try:
    importlib.import_module('app')
    print('Import app: OK')
except Exception as e:
    print('Import app: FAILED')
    import traceback
    traceback.print_exc()
    sys.exit(1)
