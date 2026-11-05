import sys

from dragshift.cli import run_cli
from dragshift.handoff import try_handoff

cli_code = run_cli(sys.argv)
if cli_code is not None:
    sys.exit(cli_code)

if try_handoff(sys.argv):
    sys.exit(0)

from dragshift.app import main  # noqa: E402

sys.exit(main())
