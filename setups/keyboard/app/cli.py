"""Public configure/emulate entry points."""
import argparse
from pathlib import Path
import sys
import webbrowser
from .server import create_server
from .session import request_stop, run
from .model import MODES


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline TCA configuration and emulation.')
    parser.add_argument('command', choices=['configure', 'emulate'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--mode', choices=MODES)
    parser.add_argument('--seconds', type=float)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--test-fixture', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.seconds is not None and args.seconds <= 0:
        parser.error('--seconds must be positive')
    try:
        if args.command == 'configure':
            server = create_server(args.root, args.test_fixture, args.mode)
            try:
                if args.no_browser:
                    print(server.url, flush=True)
                else:
                    webbrowser.open(server.url)
                    print('Local configuration opened. Keep this window open; Ctrl+C closes the server.')
                server.serve_forever()
            finally:
                server.server_close()
        elif args.stop:
            print('Stop requested. Wait for the emulation window to finish.' if request_stop(args.root / '.local') else 'No active session.')
        else:
            if args.test_fixture is not None:
                raise ValueError('Test fixtures are permitted only for the configuration server.')
            run(args.root, seconds=args.seconds, expected_mode=args.mode)
        return 0
    except KeyboardInterrupt:
        return 0
    except (ValueError, RuntimeError, OSError) as error:
        # OSError may contain private paths; keep Windows error details local to the dependency UI.
        message = 'A local file or Windows dependency is unavailable. Run configure.cmd and recheck.' if isinstance(error, OSError) else str(error)
        print(message, file=sys.stderr)
        return 1
