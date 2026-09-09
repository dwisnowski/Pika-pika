"""Fixed professional-review policy for logged power-quality events.

Independent of user-configurable log thresholds: every logged event is scored
against IEEE 1159 / ANSI C84.1-inspired severity rules so the UI always shows
whether a utility or electrician should review it.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# Defaults match pika.yaml `review:` (read-only policy; not settings-gear editable).
_DEFAULTS = {
    "interruption_pct": 10.0,
    "deep_sag_pct": 70.0,
    "damaging_swell_pct": 120.0,
    "sustained_duration_ms": 60000.0,
    "range_b_low_pct": -13.3,
    "range_b_high_pct": 5.8,
}


def _policy_from_config(config: Optional[dict]) -> Dict[str, float]:
    review = (config or {}).get("review") or {}
    out = dict(_DEFAULTS)
    for key in out:
        if key in review and review[key] is not None:
            out[key] = float(review[key])
    return out


def evaluate_event_review(
    *,
    event_type: str,
    extreme_rms_v: float,
    duration_ms: float,
    nominal_vrms: float,
    config: Optional[dict] = None,
) -> Dict[str, Any]:
    """Return needs_review / reason / guidance for one event."""
    policy = _policy_from_config(config)
    if nominal_vrms <= 0:
        nominal_vrms = 120.0

    pct_of_nominal = (extreme_rms_v / nominal_vrms) * 100.0
    et = (event_type or "").upper()

    interruption_pct = policy["interruption_pct"]
    deep_sag_pct = policy["deep_sag_pct"]
    damaging_swell_pct = policy["damaging_swell_pct"]
    sustained_ms = policy["sustained_duration_ms"]
    range_b_low = 100.0 + policy["range_b_low_pct"]
    range_b_high = 100.0 + policy["range_b_high_pct"]

    if pct_of_nominal <= interruption_pct:
        return {
            "needs_review": True,
            "review_reason": (
                f"Interruption-class: extreme RMS {extreme_rms_v:.1f} V "
                f"({pct_of_nominal:.0f}% of {nominal_vrms:.0f} V nominal)"
            ),
            "review_guidance": (
                "Contact your utility for a service outage or open-neutral "
                "investigation. If only one circuit is affected, call an "
                "electrician first."
            ),
        }

    if et == "SAG" and pct_of_nominal <= deep_sag_pct:
        return {
            "needs_review": True,
            "review_reason": (
                f"Deep sag: extreme RMS {extreme_rms_v:.1f} V "
                f"({pct_of_nominal:.0f}% ≤ {deep_sag_pct:.0f}% nominal)"
            ),
            "review_guidance": (
                "Deep sags can disrupt or stress equipment. Log time/duration "
                "and contact your utility; ask an electrician to check loose "
                "connections if the issue is limited to part of the house."
            ),
        }

    if et == "SWELL" and pct_of_nominal >= damaging_swell_pct:
        return {
            "needs_review": True,
            "review_reason": (
                f"Damaging swell: extreme RMS {extreme_rms_v:.1f} V "
                f"({pct_of_nominal:.0f}% ≥ {damaging_swell_pct:.0f}% nominal)"
            ),
            "review_guidance": (
                "High swells can damage electronics. Contact an electrician "
                "(loose neutral is a common cause) and your utility if the "
                "high voltage appears service-wide."
            ),
        }

    if duration_ms >= sustained_ms and (
        pct_of_nominal <= range_b_low or pct_of_nominal >= range_b_high
    ):
        return {
            "needs_review": True,
            "review_reason": (
                f"Sustained out-of-Range-B: {extreme_rms_v:.1f} V for "
                f"{duration_ms / 1000.0:.1f} s "
                f"(ANSI C84.1 utilization Range B ≈ "
                f"{range_b_low:.1f}–{range_b_high:.1f}% of nominal)"
            ),
            "review_guidance": (
                "Sustained voltage outside ANSI Range B warrants a utility "
                "voltage investigation. Have an electrician verify the issue "
                "is not limited to house wiring first if practical."
            ),
        }

    return {
        "needs_review": False,
        "review_reason": "",
        "review_guidance": (
            "Logged for awareness only. Mild short sags/swells are common; "
            "frequent repeats still deserve an electrician check of wiring "
            "and large loads."
        ),
    }


def review_policy_public(config: Optional[dict] = None) -> Dict[str, Any]:
    """Read-only policy snapshot for help UI / API."""
    policy = _policy_from_config(config)
    return {
        "editable": False,
        "interruption_pct": policy["interruption_pct"],
        "deep_sag_pct": policy["deep_sag_pct"],
        "damaging_swell_pct": policy["damaging_swell_pct"],
        "sustained_duration_ms": policy["sustained_duration_ms"],
        "range_b_low_pct": policy["range_b_low_pct"],
        "range_b_high_pct": policy["range_b_high_pct"],
        "summary": (
            "Professional review is recommended for interruption-class "
            f"(≤{policy['interruption_pct']:.0f}% RMS), deep sags "
            f"(≤{policy['deep_sag_pct']:.0f}%), damaging swells "
            f"(≥{policy['damaging_swell_pct']:.0f}%), or sustained "
            f"(≥{policy['sustained_duration_ms']/1000:.0f}s) voltage outside "
            "ANSI C84.1 utilization Range B."
        ),
    }
