from pathlib import Path
import resource
import sys
import traceback

from native_softmax import bootstrap


def main() -> int:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        bootstrap(Path(__file__).resolve().parents[1], Path(__file__).resolve())
    except Exception as error:
        from contract import write_json_atomic

        arguments = sys.argv[1:]
        if "--response" in arguments:
            response_index = arguments.index("--response") + 1
            if response_index < len(arguments):
                write_json_atomic(Path(arguments[response_index]), {
                    "status": "error",
                    "stage": "native_softmax_bootstrap",
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                })
        print(f"CT2_NATIVE_BOOTSTRAP_ERROR {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        return 1
    from worker import main as worker_main

    return worker_main()


if __name__ == "__main__":
    raise SystemExit(main())
