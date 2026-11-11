# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later


class TUIRenderer:
    """Beautiful Unicode & Markdown TUI Renderer for Local-Memory-RAG."""

    @staticmethod
    def status_tag(status: str) -> str:
        status = status.upper()
        if status in ("OK", "SUCCESS", "GREEN"):
            return "🟢 SUCCESS"
        elif status in ("ERROR", "FAIL", "FAILURE"):
            return "🔴 ERROR"
        elif status in ("SEARCH", "SEARCHING", "FIND"):
            return "🔍 SEARCHING"
        elif status in ("WRITE", "WRITING", "SAVE"):
            return "💾 WRITING"
        elif status in ("STATS", "INFO"):
            return "📊 STATS"
        elif status in ("INDEX", "BUILD"):
            return "⚡ INDEXING"
        elif status in ("ORGANIZE", "CLEAN", "MAINTAIN"):
            return "🧹 MAINTAINING"
        elif status in ("BOOTSTRAP", "INIT", "SETUP"):
            return "🚀 BOOTSTRAPPING"
        elif status in ("EXPLAIN", "DEBUG"):
            return "🕵️ EXPLAINING"
        elif status in ("RESTORE", "RESTORING", "SESSION"):
            return "🧠 RESTORING"
        return f"💡 {status}"

    @staticmethod
    def render_panel(
        title: str, lines: list, status: str = "OK", width: int = 70
    ) -> str:
        """Render a gorgeous heavy-bordered Unicode panel for terminal output."""
        border_top = "╔" + "═" * (width - 2) + "╗"
        border_bottom = "╚" + "═" * (width - 2) + "╝"

        tag = TUIRenderer.status_tag(status)
        header_text = f"  {title} | {tag}  "
        if len(header_text) < width - 6:
            # Center the header text in the top border
            padding_left = (width - 2 - len(header_text)) // 2
            padding_right = width - 2 - len(header_text) - padding_left
            border_top = (
                "╔" + "═" * padding_left + header_text + "═" * padding_right + "╗"
            )

        panel_lines = [border_top]
        for line in lines:
            line_str = str(line)
            # Handle lines longer than width by wrapping
            while len(line_str) > width - 4:
                chunk = line_str[: width - 4]
                panel_lines.append(f"║ {chunk.ljust(width - 4)} ║")
                line_str = line_str[width - 4 :]
            panel_lines.append(f"║ {line_str.ljust(width - 4)} ║")

        panel_lines.append(border_bottom)
        return "\n".join(panel_lines)
