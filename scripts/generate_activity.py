#!/usr/bin/env python3

import json
import math
import os
import sys
import urllib.error
import urllib.request

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "activity"

USERNAME = "VKondr0"
API_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays {
            contributionCount
          }
        }
      }
    }
  }
}
"""


THEMES = {
    "dark": {
        "background": "#101413",
        "background_end": "#18211A",
        "border": "#39483B",
        "text": "#F0EEE7",
        "muted": "#A9B9A8",
        "subtle": "#819382",
        "grid": "#4F6352",
        "divider": "#425346",
        "accent": "#C5EF80",
        "accent_dark": "#415A42",
        "contour": "#66845F",
    },
    "light": {
        "background": "#F0EEE7",
        "background_end": "#E7EAE0",
        "border": "#BBC7B7",
        "text": "#101413",
        "muted": "#536754",
        "subtle": "#607265",
        "grid": "#9BAE99",
        "divider": "#A7B5A4",
        "accent": "#547C30",
        "accent_dark": "#8FC34A",
        "contour": "#839C78",
    },
}


def fetch_contributions(token):
    payload = json.dumps({
        "query": QUERY,
        "variables": {"login": USERNAME},
    }).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "VK-INDEX",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("errors"):
        messages = [
            error.get("message", "Unknown GraphQL error")
            for error in result["errors"]
        ]
        raise RuntimeError("; ".join(messages))

    user = result.get("data", {}).get("user")

    if user is None:
        raise RuntimeError(
            f"GitHub user {USERNAME} was not found."
        )

    calendar = (
        user["contributionsCollection"]
        ["contributionCalendar"]
    )

    weeks = calendar["weeks"][-52:]

    if not weeks:
        raise RuntimeError(
            "GitHub returned no contribution weeks."
        )

    counts = []

    for week in weeks:
        total = sum(
            max(0, int(day["contributionCount"]))
            for day in week["contributionDays"]
        )
        counts.append(total)

    return counts


def create_points(counts):
    if not counts:
        return []

    left = 385
    right = 1150

    top = 140
    bottom = 240

    maximum = max(counts)

    points = []

    for index, count in enumerate(counts):
        fraction = index / max(1, len(counts) - 1)

        x = left + fraction * (right - left)

        if maximum > 0:
            intensity = math.sqrt(count / maximum)
        else:
            intensity = 0.0

        y = bottom - intensity * (bottom - top)

        points.append((x, y))

    return points


def create_mobile_points(counts):
    if not counts:
        return []

    left = 46
    right = 594

    top = 360
    bottom = 489

    maximum = max(counts)
    points = []

    for index, count in enumerate(counts):
        fraction = index / max(1, len(counts) - 1)

        x = left + fraction * (right - left)

        if maximum > 0:
            intensity = math.sqrt(count / maximum)
        else:
            intensity = 0.0

        y = bottom - intensity * (bottom - top)

        points.append((x, y))

    return points


def smooth_path(points):
    if not points:
        return ""

    commands = [
        f"M {points[0][0]:.2f} {points[0][1]:.2f}"
    ]

    for i in range(len(points) - 1):
        previous = points[max(0, i - 1)]
        current = points[i]
        following = points[i + 1]
        next_point = points[
            min(len(points) - 1, i + 2)
        ]

        step = (
            following[0] - current[0]
        ) / 3

        c1x = current[0] + step
        c1y = (
            current[1]
            + (following[1] - previous[1]) / 6
        )

        c2x = following[0] - step
        c2y = (
            following[1]
            - (next_point[1] - current[1]) / 6
        )

        commands.append(
            f"C {c1x:.2f} {c1y:.2f} "
            f"{c2x:.2f} {c2y:.2f} "
            f"{following[0]:.2f} "
            f"{following[1]:.2f}"
        )

    return " ".join(commands)


def offset_path(points, offset):
    shifted = [
        (x, y + offset)
        for x, y in points
    ]

    return smooth_path(shifted)


def render_svg(theme, counts):
    c = THEMES[theme]

    points = create_points(counts)
    main_path = smooth_path(points)

    contours = []

    for offset in (-20, -10, 10, 20):
        path = offset_path(points, offset)
        contours.append(f'<path d="{path}" />')

    contour_markup = "\n      ".join(contours)

    horizontal_grid = "\n".join(
        f'<line x1="385" y1="{y}" '
        f'x2="1150" y2="{y}" />'
        for y in (135, 180, 225, 270)
    )

    vertical_grid = "\n".join(
        f'<line x1="{x}" y1="125" '
        f'x2="{x}" y2="275" />'
        for x in range(385, 1151, 85)
    )

    total = sum(counts)

    generated = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    label = escape(
        f"{total:,} contributions "
        f"across the displayed weeks"
    )

    last_x, last_y = points[-1]

    return f"""<svg xmlns="http://www.w3.org/2000/svg"
     width="1200"
     height="350"
     viewBox="0 0 1200 350"
     role="img"
     aria-labelledby="title desc">

  <title id="title">VK / INDEX — Activity Signature</title>

  <desc id="desc">
    {label}.
    A generative visualization of GitHub activity.
    Updated {generated}.
  </desc>

  <defs>
    <linearGradient id="background" x2="1" y2="1">
      <stop offset="0%" stop-color="{c['background']}"/>
      <stop offset="100%" stop-color="{c['background_end']}"/>
    </linearGradient>

    <linearGradient id="signal" x2="1" y2="0">
      <stop offset="0%" stop-color="{c['accent_dark']}"/>
      <stop offset="55%" stop-color="{c['accent']}"/>
      <stop offset="100%" stop-color="{c['accent_dark']}"/>
    </linearGradient>

    <clipPath id="frame">
      <rect width="1200" height="350" rx="18"/>
    </clipPath>
  </defs>

  <g clip-path="url(#frame)">

    <rect width="1200"
          height="350"
          fill="url(#background)"/>

    <rect x="1" y="1"
          width="1198" height="348"
          rx="17"
          fill="none"
          stroke="{c['border']}"/>

    <rect x="45" y="43"
          width="9" height="9"
          fill="{c['accent']}"/>

    <text x="70" y="53"
          font-family="monospace"
          font-size="16"
          letter-spacing="3"
          fill="{c['accent']}">
      02 / ACTIVITY SIGNATURE
    </text>

    <text x="1150" y="53"
          text-anchor="end"
          font-family="monospace"
          font-size="12"
          letter-spacing="2"
          fill="{c['muted']}">
      GENERATIVE VISUALIZATION
    </text>

    <line x1="45" y1="81"
          x2="1155" y2="81"
          stroke="{c['divider']}"/>

    <text x="48" y="147"
          font-family="Arial, Helvetica, sans-serif"
          font-size="43"
          font-weight="800"
          letter-spacing="-1"
          fill="{c['text']}">
      ACTIVITY
    </text>

    <text x="48" y="196"
          font-family="Arial, Helvetica, sans-serif"
          font-size="43"
          font-weight="800"
          letter-spacing="-1"
          fill="{c['text']}">
      SIGNATURE
    </text>

    <rect x="48" y="218"
          width="36" height="3"
          fill="{c['accent']}"/>

    <text x="48" y="251"
          font-family="monospace"
          font-size="12"
          letter-spacing="1.3"
          fill="{c['muted']}">
      LAST 52 WEEKS
    </text>

    <text x="48" y="274"
          font-family="monospace"
          font-size="11"
          fill="{c['subtle']}">
      {total:,} CONTRIBUTIONS
    </text>

    <line x1="344" y1="114"
          x2="344" y2="287"
          stroke="{c['divider']}"/>

    <g fill="none"
       stroke="{c['grid']}"
       stroke-width="0.7"
       opacity="0.38">

      {horizontal_grid}
      {vertical_grid}

    </g>

    <g fill="none"
       stroke="{c['contour']}"
       stroke-width="1"
       opacity="0.4"
       stroke-linecap="round">

      {contour_markup}

    </g>

    <path d="{main_path}"
          fill="none"
          stroke="url(#signal)"
          stroke-width="2.6"
          stroke-linecap="round"
          stroke-linejoin="round"/>

    <circle cx="{last_x:.2f}"
            cy="{last_y:.2f}"
            r="5"
            fill="{c['accent']}"/>

    <circle cx="{last_x:.2f}"
            cy="{last_y:.2f}"
            r="11"
            fill="none"
            stroke="{c['accent']}"
            opacity="0.35"/>

    <text x="385" y="301"
          font-family="monospace"
          font-size="11"
          letter-spacing="1"
          fill="{c['subtle']}">
      52 WEEKS AGO
    </text>

    <text x="1150" y="301"
          text-anchor="end"
          font-family="monospace"
          font-size="11"
          letter-spacing="1"
          fill="{c['subtle']}">
      RECENT
    </text>

    <line x1="45" y1="320"
          x2="1155" y2="320"
          stroke="{c['divider']}"/>

    <text x="45" y="338"
          font-family="monospace"
          font-size="10"
          letter-spacing="1"
          fill="{c['subtle']}">
      VK / INDEX — GITHUB CONTRIBUTION DATA
    </text>

    <text x="1155" y="338"
          text-anchor="end"
          font-family="monospace"
          font-size="10"
          letter-spacing="1"
          fill="{c['accent']}">
      UPDATED {generated}
    </text>

  </g>
</svg>
"""


def render_mobile_svg(theme, counts):
    c = THEMES[theme]

    points = create_mobile_points(counts)
    main_path = smooth_path(points)

    contours = "\n      ".join(
        f'<path d="{offset_path(points, offset)}" />'
        for offset in (-18, -9, 9, 18)
    )

    horizontal_grid = "\n      ".join(
        f'<line x1="46" y1="{y}" '
        f'x2="594" y2="{y}" />'
        for y in (360, 403, 446, 489)
    )

    vertical_grid = "\n      ".join(
        f'<line x1="{x}" y1="345" '
        f'x2="{x}" y2="510" />'
        for x in range(46, 595, 55)
    )

    total = sum(counts)

    generated = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    label = escape(
        f"{total:,} contributions "
        f"across the displayed weeks"
    )

    last_x, last_y = points[-1]

    return f"""<svg xmlns="http://www.w3.org/2000/svg"
     width="640"
     height="620"
     viewBox="0 0 640 620"
     role="img"
     aria-labelledby="title desc">

  <title id="title">
    VK / INDEX — Mobile Activity Signature
  </title>

  <desc id="desc">
    {label}.
    Generative visualization of GitHub activity.
    Updated {generated}.
  </desc>

  <defs>
    <linearGradient id="background" x2="1" y2="1">
      <stop offset="0%" stop-color="{c['background']}"/>
      <stop offset="100%" stop-color="{c['background_end']}"/>
    </linearGradient>

    <linearGradient id="signal" x2="1" y2="0">
      <stop offset="0%" stop-color="{c['accent_dark']}"/>
      <stop offset="55%" stop-color="{c['accent']}"/>
      <stop offset="100%" stop-color="{c['accent_dark']}"/>
    </linearGradient>

    <clipPath id="frame">
      <rect width="640" height="620" rx="20"/>
    </clipPath>
  </defs>

  <g clip-path="url(#frame)">

    <!-- Background -->

    <rect width="640"
          height="620"
          fill="url(#background)"/>

    <rect x="1" y="1"
          width="638" height="618"
          rx="19"
          fill="none"
          stroke="{c['border']}"/>

    <!-- Header -->

    <rect x="34" y="36"
          width="11" height="11"
          fill="{c['accent']}"/>

    <text x="60" y="48"
          font-family="monospace"
          font-size="20"
          font-weight="bold"
          letter-spacing="1.5"
          fill="{c['accent']}">
      02 / ACTIVITY SIGNATURE
    </text>

    <text x="606" y="48"
          text-anchor="end"
          font-family="monospace"
          font-size="14"
          letter-spacing="1"
          fill="{c['muted']}">
      52 WEEKS
    </text>

    <line x1="34" y1="76"
          x2="606" y2="76"
          stroke="{c['divider']}"/>

    <!-- Title -->

    <text x="38" y="163"
          font-family="Arial, Helvetica, sans-serif"
          font-size="76"
          font-weight="900"
          letter-spacing="-2"
          fill="{c['text']}">
      ACTIVITY
    </text>

    <text x="38" y="238"
          font-family="Arial, Helvetica, sans-serif"
          font-size="76"
          font-weight="900"
          letter-spacing="-2"
          fill="{c['text']}">
      SIGNATURE
    </text>

    <rect x="40" y="259"
          width="39" height="4"
          fill="{c['accent']}"/>

    <text x="40" y="289"
          font-family="monospace"
          font-size="18"
          letter-spacing="1.2"
          fill="{c['muted']}">
      GITHUB CONTRIBUTION DATA
    </text>

    <text x="40" y="321"
          font-family="monospace"
          font-size="22"
          font-weight="bold"
          letter-spacing="1"
          fill="{c['accent']}">
      {total:,} CONTRIBUTIONS
    </text>

    <!-- Chart area -->

    <line x1="40" y1="340"
          x2="600" y2="340"
          stroke="{c['divider']}"/>

    <g fill="none"
       stroke="{c['grid']}"
       stroke-width="1"
       opacity="0.38">

      {horizontal_grid}
      {vertical_grid}

    </g>

    <!-- Activity contours -->

    <g fill="none"
       stroke="{c['contour']}"
       stroke-width="1.4"
       opacity="0.42"
       stroke-linecap="round"
       stroke-linejoin="round">

      {contours}

    </g>

    <!-- Main signature -->

    <path d="{main_path}"
          fill="none"
          stroke="url(#signal)"
          stroke-width="3.5"
          stroke-linecap="round"
          stroke-linejoin="round"/>

    <circle cx="{last_x:.2f}"
            cy="{last_y:.2f}"
            r="6"
            fill="{c['accent']}"/>

    <circle cx="{last_x:.2f}"
            cy="{last_y:.2f}"
            r="13"
            fill="none"
            stroke="{c['accent']}"
            stroke-width="1.5"
            opacity="0.35"/>

    <!-- Timeline -->

    <text x="46" y="546"
          font-family="monospace"
          font-size="16"
          letter-spacing="1"
          fill="{c['subtle']}">
      52 WEEKS AGO
    </text>

    <text x="594" y="546"
          text-anchor="end"
          font-family="monospace"
          font-size="16"
          letter-spacing="1"
          fill="{c['subtle']}">
      RECENT
    </text>

    <!-- Footer -->

    <line x1="40" y1="568"
          x2="600" y2="568"
          stroke="{c['divider']}"/>

    <text x="40" y="596"
          font-family="monospace"
          font-size="15"
          letter-spacing="1"
          fill="{c['subtle']}">
      VK / INDEX
    </text>

    <text x="600" y="596"
          text-anchor="end"
          font-family="monospace"
          font-size="15"
          letter-spacing="1"
          fill="{c['accent']}">
      UPDATED {generated}
    </text>

  </g>
</svg>
"""


def main():
    token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
    )

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is missing. "
            "Run this script with an authenticated "
            "GitHub token."
        )

    counts = fetch_contributions(token)

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    for theme in ("dark", "light"):
        desktop_svg = render_svg(theme, counts)
        mobile_svg = render_mobile_svg(theme, counts)

        outputs = {
            f"signature-{theme}.svg": desktop_svg,
            f"signature-mobile-{theme}.svg": mobile_svg,
        }

        for name, svg in outputs.items():
            destination = OUTPUT / name

            destination.write_text(
                svg,
                encoding="utf-8"
            )

            print(
                f"Generated: "
                f"{destination.relative_to(ROOT)}"
            )

    print(
        f"Real contributions in selected weeks: "
        f"{sum(counts)}"
    )


if __name__ == "__main__":
    try:
        main()

    except (
        RuntimeError,
        KeyError,
        ValueError,
        urllib.error.URLError,
    ) as error:
        print(
            f"Activity generation failed: {error}",
            file=sys.stderr
        )
        sys.exit(1)