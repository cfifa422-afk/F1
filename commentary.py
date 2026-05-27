import random
from typing import List, Optional


def generate_turn_commentary(
    turn: int,
    lap: int,
    total_laps: int,
    p1_name: str,
    p2_name: str,
    p1_choice: str,
    p2_choice: str,
    gap: float,
    event: Optional[str],
    p1_fuel: float,
    p2_fuel: float,
    p1_tire_wear: float,
    p2_tire_wear: float,
    p1_tire_type: str,
    p2_tire_type: str,
    p1_leading: bool,
    weather: str,
) -> List[str]:
    lines: List[str] = []
    leader  = p1_name if p1_leading else p2_name
    trailer = p2_name if p1_leading else p1_name

    # Lap milestones
    if turn == 1 and lap == 1:
        lines.append(
            f"**LIGHTS OUT AND AWAY WE GO!** {p1_name} and {p2_name} launch off the grid!"
        )
        return lines

    if lap == total_laps and (turn - 1) % 4 == 0 and turn > 1:
        lines.append(
            "**FINAL LAP BEGINS!** Every tenth, every decision — it all matters NOW!"
        )

    # Track events (highest priority)
    if event:
        if "Rain" in event:
            lines.append(
                "**RAIN! WEATHER CHANGE!** The circuit is getting wet — "
                "slick tyres are a LIABILITY. Someone needs to pit for wets, and FAST!"
            )
        elif "DRS" in event:
            lines.append(
                f"**DRS ZONE!** The drag reduction is open — {trailer} has a "
                "tow opportunity here. Can they make a move stick?"
            )
        elif "Safety" in event:
            lines.append(
                "**SAFETY CAR! SAFETY CAR!** The field is bunching. "
                "Strategy calls are being made on the pitwall RIGHT NOW — "
                "this could completely rewrite the race order!"
            )

    # Choice commentary
    p1_pit  = p1_choice == "pit_stop"
    p2_pit  = p2_choice == "pit_stop"
    p1_push = p1_choice == "accelerate"
    p2_push = p2_choice == "accelerate"
    p1_lift = p1_choice == "slow_down"
    p2_lift = p2_choice == "slow_down"

    if p1_pit and p2_pit:
        lines.append(
            "Both cars peel into the pits at the same time! "
            "The race effectively RESETS — track position gone, fresh tyres on both sides!"
        )
    elif p1_pit and not p2_pit:
        if gap < 0:
            lines.append(
                f"{p1_name} PITS FROM THE LEAD! A daring undercut — "
                f"can fresh rubber beat {p2_name}'s track position?"
            )
        else:
            lines.append(
                f"{p1_name} dives into the pitlane! The overcut strategy — "
                "will it bridge the gap, or surrender too many seconds?"
            )
    elif p2_pit and not p1_pit:
        if gap > 0:
            lines.append(
                f"{p2_name} PITS FROM THE FRONT! Sacrificing the lead for rubber. "
                "The fastest stops in business — every tenth in that box counts!"
            )
        else:
            lines.append(
                f"{p2_name} makes the call to pit — "
                f"fresh tyres could be the key to hunting down {p1_name}!"
            )
    elif p1_push and p2_push:
        _phrases = [
            "flat out, absolutely on the ragged edge",
            "at the absolute limit of adhesion",
            "pushing like there is NO tomorrow",
        ]
        lines.append(
            f"BOTH cars are {random.choice(_phrases)}! "
            "Neither driver willing to give a single tenth — this is PURE racing!"
        )
    elif p1_push and p2_lift:
        lines.append(
            f"{p1_name} goes on the attack! Maximum throttle while "
            f"{p2_name} looks after the tyres — the gap is about to SHIFT!"
        )
    elif p2_push and p1_lift:
        lines.append(
            f"{p2_name} turns UP the pressure! {p1_name} is in tyre-save mode — "
            "is that a mistake? This could be the moment the race TURNS!"
        )
    elif p1_lift and p2_lift:
        lines.append(
            "Both drivers in conservation mode — fuel management, tyre management. "
            "The real race will be fought in the final laps. Patience is a weapon here."
        )
    else:
        _generic = [
            f"{p1_name} and {p2_name} trading identical lap times — "
            "inches apart on pace, but the gap refuses to change.",
            "Consistent, precise driving from both camps. "
            "Something has to give — one slip, one mistake, and it's over.",
            f"The tactical chess match continues. {leader} is managing brilliantly, "
            f"but {trailer} is watching every move.",
        ]
        lines.append(random.choice(_generic))

    # Gap drama
    if abs(gap) < 0.3:
        lines.append(
            f"**{abs(gap):.2f} SECONDS BETWEEN THEM — SIDE BY SIDE RACING!** "
            "One missed apex and it's done. INCREDIBLE!"
        )
    elif abs(gap) < 1.0:
        _close = [
            f"The gap reads **{abs(gap):.2f}s** — {leader} can hear "
            f"{trailer}'s engine in their mirrors!",
            f"Just **{abs(gap):.2f}s** in it — one DRS zone, one lock-up, "
            "and this lead evaporates entirely.",
        ]
        lines.append(random.choice(_close))
    elif abs(gap) > 5.0:
        lines.append(
            f"{leader} has built a **{abs(gap):.1f}s** cushion — "
            "beginning to manage the gap rather than push flat out."
        )

    # Tyre cliff
    if max(p1_tire_wear, p2_tire_wear) > 78:
        worn = p1_name if p1_tire_wear > p2_tire_wear else p2_name
        lines.append(
            f"{worn}'s tyres are past the cliff edge — "
            "lap times are FALLING OFF. A pit stop isn't optional anymore, it's SURVIVAL!"
        )

    # Fuel alarm
    if min(p1_fuel, p2_fuel) < 22:
        low = p1_name if p1_fuel < p2_fuel else p2_name
        lines.append(
            f"**FUEL CRITICAL** for {low}! The delta message is flashing — "
            "lift and coast or face a catastrophic engine failure!"
        )

    # Wet tyres on dry / vice versa
    if weather == "rain":
        wrong = []
        if p1_tire_type in ("soft", "medium", "hard"):
            wrong.append(p1_name)
        if p2_tire_type in ("soft", "medium", "hard"):
            wrong.append(p2_name)
        if wrong:
            lines.append(
                f"{' & '.join(wrong)} on DRY rubber in the WET — "
                "every corner is a lottery. The pitwall MUST react!"
            )

    # Last-lap closer
    if lap == total_laps and (turn % 4 == 3):
        lines.append(
            f"White flag waved — ONE MORE LAP. "
            f"{leader} needs to hold it together. {trailer} needs a miracle. "
            "This is what RACING is all about!"
        )

    return lines[:4]


def format_commentary(lines: List[str]) -> str:
    """Format commentary lines as plain text for a Discord embed description."""
    if not lines:
        return "Race in progress..."
    return "\n\n".join(lines)
