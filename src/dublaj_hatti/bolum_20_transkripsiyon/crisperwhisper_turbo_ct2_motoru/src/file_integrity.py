import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys
import time


host_python_env = 'DUBLAJ_CT2_HOST_PYTHON'
buffer_bytes = 8 * 1024 * 1024
native_minimum_bytes = 64 * 1024 * 1024


def buffered_sha256_file(path):
    digest = hashlib.sha256()
    buffer = bytearray(buffer_bytes)
    view = memoryview(buffer)
    with Path(path).open('rb', buffering=0) as handle:
        while size := handle.readinto(buffer):
            digest.update(view[:size])
    return digest.hexdigest()


def windows_mount_path(path):
    value = str(Path(path).resolve())
    match = re.fullmatch(r'/mnt/([a-zA-Z])/(.+)', value)
    if match is None or any(ord(char) < 32 for char in value):
        raise ValueError('An absolute Windows-mounted file is required')
    return str(PureWindowsPath(match[1].upper() + ':/', *match[2].split('/')))


class FileIntegrity:
    def __init__(self):
        self.host_python = os.environ.get(host_python_env, '')
        self.measurements = []

    def __call__(self, path):
        path = Path(path)
        started = time.perf_counter()
        method = 'buffered_full_sha256'
        fallback = None
        try:
            native = sys.platform == 'linux' and self.host_python and path.stat().st_size >= native_minimum_bytes
            if native:
                try:
                    native_path = windows_mount_path(path)
                    helper = windows_mount_path(Path(__file__).with_name('file_integrity.py'))
                    completed = subprocess.run(
                        [self.host_python, '-I', '-S', helper, '--hash-file', native_path],
                        capture_output=True,
                        check=True,
                        timeout=120,
                    )
                    result = json.loads(completed.stdout)
                    digest = result['sha256']
                    if not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None:
                        raise ValueError('Invalid full-file SHA256 response')
                    if result['size_bytes'] != path.stat().st_size:
                        raise ValueError('Native hashing file size changed')
                    method = 'host_python_full_sha256'
                    return digest
                except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
                    fallback = type(error).__name__
            return buffered_sha256_file(path)
        finally:
            self.measurements.append({
                'file': path.name,
                'method': method,
                'seconds': time.perf_counter() - started,
                'fallback': fallback,
            })


def main():
    if len(sys.argv) != 3 or sys.argv[1] != '--hash-file':
        raise ValueError('Expected --hash-file and an absolute path')
    path = Path(sys.argv[2])
    if not path.is_absolute():
        raise ValueError('An absolute path is required')
    digest = buffered_sha256_file(path)
    print(json.dumps({'sha256': digest, 'size_bytes': path.stat().st_size}))


if __name__ == '__main__':
    main()
