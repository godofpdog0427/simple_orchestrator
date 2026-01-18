#!/usr/bin/env python3
"""
SealMascot - CLI Block Art Seal (側躺版)
用於 Claude Code-like 工具的吉祥物
"""

import sys

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # 256 color mode for better gradients
    @staticmethod
    def fg(code):
        return f"\033[38;5;{code}m"
    
    @staticmethod
    def bg(code):
        return f"\033[48;5;{code}m"


def print_seal(message: str = "我愛海豹 🦭"):
    """Print the lying seal mascot with block characters."""
    
    r = Colors.RESET
    
    # Color palette (256 color)
    body = Colors.fg(251)      # light gray
    dark = Colors.fg(245)      # darker gray for shading
    belly = Colors.fg(255)     # white belly
    nose = Colors.fg(236)      # dark nose
    eye = Colors.fg(16)        # black eye
    blush = Colors.fg(217)     # pink blush
    cyan = Colors.fg(45)       # cyan accent
    water = Colors.fg(39)      # water blue
    
    seal = f"""
{cyan}  ･ﾟ✧ {Colors.fg(255)}SealMascot{r} {cyan}✧ﾟ･{r}

{body}                ██████{r}
{body}        ████████{belly}██████{body}████{r}
{body}      ██{belly}████████████████{body}████{r}
{body}    ██{belly}██████████████████████{body}██{r}
{body}   ██{belly}████{eye}██{belly}██████{nose}████{nose}{belly}██████{body}████{r}
{body}   ██{belly}████{eye}██{belly}██████{nose}████{belly}████████{body}██{dark}██{r}
{body}  ██{belly}██████████████████████████{body}██{r}
{body}  ██{belly}██{blush}██{belly}████████████████████{body}████{r}
{body}   ██{belly}████████████████████████{body}██{r}
{body}    ████{belly}████████████████{body}██████{r}
{body}      ████████████████████████{r}
{body}    ████{r}  {body}████████████{r}  {body}████{r}
{water}  ~~~{r}    {water}~~~~~~~~~~~~{r}    {water}~~~{r}

      {cyan}{Colors.BOLD}{message}{r}
"""
    print(seal)


def print_seal_mini():
    """Compact 3-line version."""
    c = Colors
    r = c.RESET
    body = c.fg(251)
    belly = c.fg(255)
    eye = c.fg(16)
    cyan = c.fg(45)
    
    mini = f"""{body}  ▄███{belly}██{body}███▄{r}
{body} █{belly}█{eye}●{belly}███{eye}▪{belly}██{body}██▄{r}
{body}  ▀▀{r} {body}▀▀▀▀▀{r} {body}▀▀{r} {cyan}🦭{r}"""
    print(mini)


def print_seal_compact():
    """Single line status indicator."""
    c = Colors
    print(f"{c.fg(251)}▄█{c.fg(16)}●{c.fg(251)}█▄{c.RESET} {c.fg(45)}🦭{c.RESET}")


def print_seal_thinking():
    """Thinking indicator."""
    c = Colors
    print(f"{c.fg(251)}▄█{c.fg(16)}●{c.fg(251)}█▄{c.RESET} {c.fg(45)}...{c.RESET}")


def print_seal_success():
    """Success indicator."""
    c = Colors
    print(f"{c.fg(251)}▄█{c.fg(16)}◠{c.fg(251)}█▄{c.RESET} {c.fg(82)}✓{c.RESET}")


def print_seal_error():
    """Error indicator."""
    c = Colors
    print(f"{c.fg(251)}▄█{c.fg(16)}•{c.fg(251)}█▄{c.RESET} {c.fg(196)}✗{c.RESET}")


def print_banner():
    """Startup banner with seal."""
    c = Colors
    r = c.RESET
    cyan = c.fg(45)
    white = c.fg(255)
    gray = c.fg(245)
    body = c.fg(251)
    belly = c.fg(255)
    eye = c.fg(16)
    
    banner = f"""
{cyan}╔═══════════════════════════════════════════════════╗{r}
{cyan}║{r}                                                   {cyan}║{r}
{cyan}║{r}  {body}        ██████{r}                                  {cyan}║{r}
{cyan}║{r}  {body}████████{belly}██████{body}████{r}   {white}{c.BOLD}SealMass{r}                {cyan}║{r}
{cyan}║{r}  {body}██{belly}██{eye}██{belly}██{eye}█{belly}█{body}██{belly}██████{body}██{r}   {gray}我愛海豹 🦭{r}            {cyan}║{r}
{cyan}║{r}  {body}██{belly}████████████████{body}██{r}   {gray}CLI Agent Tool{r}          {cyan}║{r}
{cyan}║{r}  {body}  ████████████████{r}                              {cyan}║{r}
{cyan}║{r}                                                   {cyan}║{r}
{cyan}╚═══════════════════════════════════════════════════╝{r}
"""
    print(banner)


def print_pixel_seal():
    """Pixel art style seal (larger, more detailed)."""
    c = Colors
    r = c.RESET
    
    # Using background colors for true pixel look
    _ = r + "  "  # transparent
    B = c.bg(251) + "  " + r  # body gray
    D = c.bg(245) + "  " + r  # dark gray
    W = c.bg(255) + "  " + r  # white belly
    E = c.bg(16) + "  " + r   # eye black
    N = c.bg(236) + "  " + r  # nose
    P = c.bg(217) + "  " + r  # pink blush
    
    pixel = f"""
{_}{_}{_}{_}{_}{_}{B}{B}{B}{_}{_}{_}{_}{_}
{_}{_}{_}{B}{B}{B}{W}{W}{W}{B}{B}{B}{_}{_}
{_}{_}{B}{W}{E}{W}{W}{W}{N}{N}{W}{W}{B}{_}
{_}{B}{W}{W}{W}{W}{W}{W}{W}{W}{W}{W}{B}{D}
{_}{B}{W}{P}{W}{W}{W}{W}{W}{W}{W}{W}{B}{D}
{_}{_}{B}{W}{W}{W}{W}{W}{W}{W}{W}{B}{B}{_}
{_}{_}{_}{B}{B}{B}{B}{B}{B}{B}{B}{_}{_}{_}
{_}{_}{B}{B}{_}{_}{B}{B}{_}{_}{B}{B}{_}{_}
"""
    print(pixel)


# Animation frames for spinner
SEAL_FRAMES = [
    "▄█●█▄",
    "▄█◐█▄", 
    "▄█◓█▄",
    "▄█●█▄",
    "▄█◑█▄",
    "▄█◒█▄",
]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "banner":
            print_banner()
        elif cmd == "mini":
            print_seal_mini()
        elif cmd == "compact":
            print_seal_compact()
        elif cmd == "thinking":
            print_seal_thinking()
        elif cmd == "success":
            print_seal_success()
        elif cmd == "error":
            print_seal_error()
        elif cmd == "pixel":
            print_pixel_seal()
        else:
            print_seal(cmd)
    else:
        print_seal()
