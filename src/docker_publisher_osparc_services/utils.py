import asyncio
from typing import Sequence

from .exceptions import CommandFailedException

MASK = "**********"


def _redact(text: str, secret_values: Sequence[str]) -> str:
    """replaces every known secret occurrence in text with a mask"""
    for secret in secret_values:
        if secret:
            text = text.replace(secret, MASK)
    return text


async def _command(
    command: str, live_output: bool = False, secret_values: Sequence[str] = (), **kwargs
) -> str:
    print(f"$ '{_redact(command, secret_values)}'")
    proc = await asyncio.create_subprocess_exec(
        *command.split(" "),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        **kwargs,
    )
    decoded_stdout = ""
    while True:
        line = await proc.stdout.readline()
        if not line:
            break

        decoded_line = line.decode("utf-8")
        if live_output:
            print(_redact(decoded_line, secret_values), end="")
        decoded_stdout += decoded_line

    await proc.wait()

    if proc.returncode != 0:
        print(f"STDOUT: {_redact(decoded_stdout, secret_values)}")
        msg = f"{_redact(command, secret_values)} failed, check logs above"
        raise CommandFailedException(msg)

    return decoded_stdout


async def command_output(
    cmd: str, secret_values: Sequence[str] = (), **kwargs
) -> str:
    return await _command(cmd, secret_values=secret_values, **kwargs)
