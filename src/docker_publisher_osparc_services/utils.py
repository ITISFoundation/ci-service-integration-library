import asyncio

from .exceptions import CommandFailedException


async def _command(command: str, live_output: bool = False, **kwargs) -> str:
    print(f"$ '{command}'")
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
            print(decoded_line, end="")
        decoded_stdout += decoded_line

    await proc.wait()

    if proc.returncode != 0:
        print(f"STDOUT: {decoded_stdout}")
        raise CommandFailedException("Check logs above")

    return decoded_stdout


async def command_output(cmd: str, **kwargs) -> str:
    return await _command(cmd, **kwargs)
