"""bobframes error types + exit-code map (ARCHITECTURE §4).

Exit codes: 0 success · 1 pipeline/build failure · 2 user error (argparse-native) ·
3 external tool missing · 4 interrupted (Ctrl+C, timeout).

Raised errors carry their own ``exit_code``; ``cli.main`` catches ``BobFramesError`` and
returns it (c06). The exit-code constants are the single source of truth — callers map by
``e.exit_code`` rather than re-deriving the integers.
"""

from __future__ import annotations

EXIT_OK = 0
EXIT_FAILURE = 1        # pipeline/build failure (lint hit, replay nonzero, schema mismatch)
EXIT_USER_ERROR = 2     # user error (argparse-native)
EXIT_TOOL_MISSING = 3   # external tool not found
EXIT_INTERRUPTED = 4    # Ctrl+C / timeout


class BobFramesError(Exception):
    """Base for bobframes-raised errors that map to a CLI exit code."""

    exit_code = EXIT_FAILURE


class PipelineError(BobFramesError):
    """Ingest/build pipeline failed (lint hit, replay nonzero, schema mismatch)."""

    exit_code = EXIT_FAILURE


class ToolNotFound(BobFramesError):
    """An external tool (``renderdoccmd`` / ``qrenderdoc``) could not be resolved.

    ``attempts`` is the ordered list of ``(desc, path, kind)`` tried by
    ``config.resolve_tool``; ``str(self)`` renders the ARCHITECTURE §5 error block.
    ``kind`` ∈ {'env', 'config', 'path', 'file'} drives the per-line status.
    """

    exit_code = EXIT_TOOL_MISSING

    def __init__(self, tool: str, attempts: list[tuple[str, str | None, str]] | None = None):
        self.tool = tool
        self.attempts = attempts or []
        super().__init__(self.format_message())

    def format_message(self) -> str:
        lines = [f'bobframes: {self.tool} not found.', '', 'Tried (in order):']
        for desc, path, kind in self.attempts:
            if kind == 'path':
                status = '(not on PATH)'
            elif kind == 'file':
                status = '(not present)'      # a filesystem candidate that didn't resolve
            else:
                status = '(not present)' if path else '(unset)'  # env / config
            lines.append(f'  {desc:<58} {status}')
        env_var = f'BOBFRAMES_{self.tool.upper()}'
        lines += [
            '',
            'Fix one of:',
            f"  $env:{env_var} = 'C:\\path\\to\\{self.tool}.exe'",
            '  bobframes check --write-config        # writes a stub config',
            '  Install RenderDoc: https://renderdoc.org/builds',
        ]
        return '\n'.join(lines)
