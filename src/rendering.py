"""
Core rendering module using Pygame.

Handles display initialization (TFT / HDMI auto-scaling with preserved
aspect ratio), static background, fonts, logo and the main render loop.
"""

from __future__ import annotations

import atexit
import logging
import time
from typing import Dict, Optional

import pygame

from src.constants import (
    CHART_H,
    CHART_W,
    CHART_X,
    CHART_Y,
    COLOR_BLACK,
    COLOR_DARK_GREEN,
    COLOR_GRAY,
    COLOR_GREEN,
    COLOR_GRID,
    COLOR_ORANGE,
    COLOR_RED,
    COLOR_WHITE,
    DIM_ALPHA,
    FPS,
    MARQUEE_H,
    MARQUEE_Y,
    SCREEN_H,
    SCREEN_W,
    STALE_WARN_SEC,
)
from src.data import AppState
from src.helpers import (
    format_difficulty,
    format_hashrate,
    format_network_hashrate,
    get_ws_status_color,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level display objects (initialized by init_pygame)
# ---------------------------------------------------------------------------

screen: Optional[pygame.Surface] = None
logical_screen: Optional[pygame.Surface] = None
BG: Optional[pygame.Surface] = None
DIM: Optional[pygame.Surface] = None
PARASITE_LOGO: Optional[pygame.Surface] = None
clock: Optional[pygame.time.Clock] = None
FONTS: Dict[str, pygame.font.Font] = {}

scale_factor: float = 1.0
scaled_w: int = 0
scaled_h: int = 0
offset_x: int = 0
offset_y: int = 0


def init_pygame(logo_path: str) -> None:
    """
    Initialize Pygame, create the display surface, fonts, static background
    and load the Parasite logo.

    Args:
        logo_path: Absolute path to the logo image.
    """
    global screen, logical_screen, BG, DIM, PARASITE_LOGO, clock, FONTS
    global scale_factor, scaled_w, scaled_h, offset_x, offset_y

    pygame.init()

    try:
        screen = pygame.display.set_mode(
            (0, 0), pygame.FULLSCREEN | pygame.NOFRAME
        )
        logger.info("Pygame display mode set successfully")
    except Exception as err:
        logger.critical("Failed to set display mode: %s", err)
        raise SystemExit(1) from err

    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    # Physical size -> scale to logical 480x320 while preserving aspect ratio
    physical_w, physical_h = screen.get_size()
    scale_x = physical_w / SCREEN_W
    scale_y = physical_h / SCREEN_H
    scale_factor = min(scale_x, scale_y)
    scaled_w = int(SCREEN_W * scale_factor)
    scaled_h = int(SCREEN_H * scale_factor)
    offset_x = (physical_w - scaled_w) // 2
    offset_y = (physical_h - scaled_h) // 2

    logical_screen = pygame.Surface((SCREEN_W, SCREEN_H))

    # Fonts (must be created after pygame.init)
    try:
        FONTS = {
            "big": pygame.font.SysFont("dejavusans medium", 62, bold=True),
            "mid": pygame.font.SysFont("dejavusans", 22),
            "pool": pygame.font.SysFont("dejavusans", 16),
            "tiny": pygame.font.SysFont("dejavusans", 15),
            "micro": pygame.font.SysFont("dejavusans", 12),
            "hr": pygame.font.SysFont("dejavusans", 16),
            "price": pygame.font.SysFont("dejavusans", 21),
            "label": pygame.font.SysFont("dejavusans", 8),
        }
        for name, font in FONTS.items():
            if font is None:
                raise RuntimeError(f"Font '{name}' failed to initialize")
        logger.info("All fonts loaded successfully")
    except Exception as err:
        logger.critical("Failed to load fonts: %s", err)
        raise SystemExit(1) from err

    # Static background + chart grid
    BG = pygame.Surface((SCREEN_W, SCREEN_H))
    BG.fill(COLOR_BLACK)
    for i in range(1, 4):
        y = CHART_Y + i * (CHART_H / 4)
        pygame.draw.line(
            BG,
            COLOR_GRID,
            (CHART_X + 4, y),
            (CHART_X + CHART_W - 4, y),
            1,
        )

    # Dimming overlay for the marquee area
    DIM = pygame.Surface((SCREEN_W, SCREEN_H))
    DIM.fill(COLOR_BLACK)
    DIM.set_alpha(DIM_ALPHA)

    # Logo
    try:
        img = pygame.image.load(logo_path).convert_alpha()
        PARASITE_LOGO = pygame.transform.smoothscale(img, (70, 16))
        logger.info("Parasite logo loaded from %s", logo_path)
    except Exception as err:
        logger.warning("Cannot load logo from %s: %s", logo_path, err)
        PARASITE_LOGO = None


def run_render_loop(state: AppState) -> None:
    """
    Main rendering loop.

    Draws the dashboard at the configured FPS. All drawing is performed
    on the logical 480x320 surface and then scaled/blitted to the physical
    display when necessary.
    """
    def _cleanup() -> None:
        logger.info("Shutting down Pygame...")
        if pygame.get_init():
            pygame.quit()

    atexit.register(_cleanup)

    assert logical_screen is not None
    assert screen is not None
    assert BG is not None
    assert DIM is not None
    assert clock is not None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit(0)

        now = time.time()
        logical_screen.blit(BG, (0, 0))

        if PARASITE_LOGO:
            logical_screen.blit(PARASITE_LOGO, (10, 8))

        # Pool line
        with state.parasite_lock:
            pool_text = (
                f"POOL: {state.parasite['pool_hashrate_str']} - "
                f"{state.parasite['pool_best_diff_str']}"
            )
        pool_surf = FONTS["pool"].render(pool_text, True, COLOR_WHITE)
        logical_screen.blit(
            pool_surf, ((SCREEN_W - pool_surf.get_width()) // 2, 18)
        )

        # WebSocket status dot
        ws_col = get_ws_status_color()
        pygame.draw.circle(logical_screen, ws_col, (SCREEN_W - 13, 14), 3)

        # Miners count
        with state.parasite_lock:
            miners_text = f"Miners: {state.parasite['user_workers']}"
        miners_surf = FONTS["micro"].render(miners_text, True, COLOR_WHITE)
        logical_screen.blit(
            miners_surf, (SCREEN_W - miners_surf.get_width() - 23, 6)
        )

        # Rank / Work / Uptime + big hashrate line
        with state.parasite_lock:
            hr_str = state.parasite["user_hashrate_str"]
            diff_str = format_difficulty(state.parasite["user_best_diff_float"])
            age = now - state.parasite["last_success_time"]
            color = (
                COLOR_ORANGE
                if age > STALE_WARN_SEC or state.parasite["user_hashrate_th"] < 0.05
                else COLOR_WHITE
                if state.parasite["user_workers"] > 0
                else COLOR_GRAY
            )
            rank_line = (
                f"RANK: {state.parasite['user_rank']} | "
                f"WORK: {state.parasite['user_work']} | "
                f"UPTIME: {state.parasite['user_uptime']}"
            )
        rank_surf = FONTS["hr"].render(rank_line, True, color)
        logical_screen.blit(
            rank_surf, ((SCREEN_W - rank_surf.get_width()) // 2, 50)
        )

        big_surf = FONTS["big"].render(f"{hr_str} - {diff_str}", True, color)
        logical_screen.blit(
            big_surf, ((SCREEN_W - big_surf.get_width()) // 2, 80)
        )

        # BTC price + chart
        with state.data_lock:
            ticker = (
                state.binance
                if state.binance.is_fresh(now)
                else state.kraken
                if state.kraken.is_fresh(now)
                else None
            )

        if ticker:
            price_str = f"${ticker.price:.2f}"
            price_col = COLOR_GREEN if ticker.change_24h >= 0 else COLOR_RED
            price_surf = FONTS["price"].render(price_str, True, price_col)
            logical_screen.blit(
                price_surf, ((SCREEN_W - price_surf.get_width()) // 2, 132)
            )

            with state.parasite_lock:
                hr_vals = list(state.hash_history)
                recent_peaks = list(state.recent_shares)
                hist_points = list(state.historical_hashrate)

            # Y-axis scales
            if hist_points:
                hr_values = [hr for _, hr in hist_points]
                min_hr = min(hr_values) if hr_values else 0.0
                max_hr = max(hr_values) if hr_values else 2.0
            elif hr_vals:
                min_hr = min(hr_vals)
                max_hr = max(hr_vals)
            else:
                min_hr = 0.0
                max_hr = 2.0

            hr_range = max(max_hr - min_hr, 0.2)
            if hr_range < 0.2:
                mid = (min_hr + max_hr) / 2
                min_hr = max(0.0, mid - 0.1)
                max_hr = mid + 0.1
                hr_range = 0.2

            if recent_peaks:
                diffs = [d for _, d in recent_peaks if d > 0]
                min_d = min(diffs) if diffs else 0.0
                max_d = max(diffs) if diffs else 1e6
                d_range = max(max_d - min_d, 1e5) if diffs else 1e6
            else:
                min_d = max_d = d_range = 0.0

            def val_to_y(v: float, vmin: float, vmax: float, vrng: float) -> int:
                if vrng <= 0:
                    return CHART_Y + CHART_H // 2
                norm = max(0.0, min(1.0, (v - vmin) / vrng))
                return CHART_Y + CHART_H - 24 - int(norm * (CHART_H - 44))

            # Historical hashrate curve
            if hist_points:
                points = []
                min_ts = hist_points[0][0]
                max_ts = hist_points[-1][0]
                time_span = max(max_ts - min_ts, 1.0)

                for ts, hr in hist_points:
                    norm_x = (ts - min_ts) / time_span
                    x = CHART_X + int(norm_x * (CHART_W - 1))
                    y = val_to_y(hr, min_hr, max_hr, hr_range) - CHART_Y
                    points.append((x, y))

                if len(points) >= 2:
                    line_surf = pygame.Surface((CHART_W, CHART_H), pygame.SRCALPHA)
                    for offset, alpha in ((1.0, 30), (0.0, 60), (0.0, 255)):
                        col_a = (*color[:3], alpha)
                        pts = (
                            [(px + offset, py + offset) for px, py in points]
                            if offset
                            else points
                        )
                        width = 5 if offset else 3
                        pygame.draw.lines(line_surf, col_a, False, pts, width)
                    logical_screen.blit(line_surf, (CHART_X, CHART_Y))

            elif len(hr_vals) >= 2:
                points = []
                for i, v in enumerate(hr_vals):
                    x = int(i / (len(hr_vals) - 1) * (CHART_W - 1))
                    y = val_to_y(v, min_hr, max_hr, hr_range) - CHART_Y
                    points.append((x, y))

                line_surf = pygame.Surface((CHART_W, CHART_H), pygame.SRCALPHA)
                for offset, alpha in ((1.0, 30), (0.0, 60), (0.0, 255)):
                    col_a = (*color[:3], alpha)
                    pts = (
                        [(px + offset, py + offset) for px, py in points]
                        if offset
                        else points
                    )
                    width = 5 if offset else 3
                    pygame.draw.lines(line_surf, col_a, False, pts, width)
                logical_screen.blit(line_surf, (CHART_X, CHART_Y))

            # Red dots = recent high-diff shares
            if recent_peaks:
                timestamps = [ts for ts, _ in recent_peaks]
                min_ts = min(timestamps)
                max_ts = max(timestamps)
                time_span = max(max_ts - min_ts, 2700.0)  # at least ~45 min

                padding_left = padding_right = 32
                eff_w = CHART_W - padding_left - padding_right

                for ts, diff in sorted(recent_peaks, key=lambda x: x[0]):
                    norm_x = max(0.0, min(1.0, (ts - min_ts) / time_span))
                    x = CHART_X + padding_left + int(norm_x * eff_w)
                    y = val_to_y(diff, min_d, max_d, d_range)
                    pygame.draw.circle(logical_screen, COLOR_RED, (x, y), 3)

            # Axis labels
            lbl = FONTS["label"]
            logical_screen.blit(
                lbl.render(format_hashrate(max_hr), True, COLOR_GRAY),
                (CHART_X + 4, CHART_Y - 2),
            )
            logical_screen.blit(
                lbl.render(format_hashrate(min_hr), True, COLOR_GRAY),
                (CHART_X + 4, CHART_Y + CHART_H - 9),
            )
            max_d_lbl = lbl.render(format_difficulty(max_d), True, COLOR_RED)
            logical_screen.blit(
                max_d_lbl,
                (CHART_X + CHART_W - 4 - max_d_lbl.get_width(), CHART_Y - 2),
            )
            min_d_lbl = lbl.render(format_difficulty(min_d), True, COLOR_RED)
            logical_screen.blit(
                min_d_lbl,
                (
                    CHART_X + CHART_W - 4 - min_d_lbl.get_width(),
                    CHART_Y + CHART_H - 9,
                ),
            )
        else:
            no_data = FONTS["mid"].render("No recent data", True, COLOR_GRAY)
            logical_screen.blit(
                no_data, ((SCREEN_W - no_data.get_width()) // 2, 139)
            )

        # Mempool marquee
        pygame.draw.rect(
            logical_screen, COLOR_DARK_GREEN, (0, MARQUEE_Y, SCREEN_W, MARQUEE_H)
        )

        with state.mempool_lock:
            m = state.mempool.copy()

        if m["fees_sats_vb"] is not None:
            parts = [
                f"{m['fees_sats_vb']:.1f} sat/vB",
                str(m["block_height"] or "?"),
            ]
            if m["mining_pool"]:
                parts.append(m["mining_pool"])
            if m["network_hashrate_eh"] is not None:
                parts.append(format_network_hashrate(m["network_hashrate_eh"]))
            if m["network_difficulty"] is not None:
                parts.append(format_difficulty(m["network_difficulty"]))
            text = " | ".join(parts)
            col = COLOR_WHITE
        else:
            text = "Loading mempool..."
            col = COLOR_GRAY

        font_sz = 16
        while font_sz >= 6:
            f = pygame.font.SysFont("dejavusans", font_sz)
            s = f.render(text, True, col)
            if s.get_width() <= SCREEN_W - 16:
                break
            font_sz -= 1

        y = MARQUEE_Y + (MARQUEE_H - s.get_height()) // 2 + 1
        logical_screen.blit(s, ((SCREEN_W - s.get_width()) // 2, y))

        logical_screen.blit(DIM, (0, 0))

        # Output to physical screen
        if scale_factor == 1.0:
            screen.blit(logical_screen, (0, 0))
        else:
            scaled = pygame.transform.smoothscale(
                logical_screen, (scaled_w, scaled_h)
            )
            screen.blit(scaled, (offset_x, offset_y))

        pygame.display.update()
        clock.tick(FPS)
        pygame.event.pump()
