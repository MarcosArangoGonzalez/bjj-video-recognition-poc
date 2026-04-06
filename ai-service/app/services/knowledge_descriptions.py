from __future__ import annotations


def humanize_label(label: str) -> str:
    return (label or "").replace("_", " ").strip().title()


DESCRIPTION_CATALOG: dict[str, dict[str, dict[str, object]]] = {
    "POSITION": {
        "side_control": {
            "description": "The top player has passed the legs and established chest-to-chest control from the side, limiting the bottom player's ability to recover guard.",
            "visuals": [
                "Top player's chest is past the bottom player's leg line",
                "Bodies are perpendicular or chest-to-chest from the side",
                "Bottom player remains pinned underneath",
            ],
        },
        "mount": {
            "description": "The top player is straddling the torso with hips over the opponent, controlling from a dominant mounted position.",
            "visuals": [
                "Top player is above the torso facing the head",
                "Legs are straddling the opponent's body",
                "Bottom player carries the attacker's weight underneath",
            ],
        },
        "back": {
            "description": "The attacker has moved behind the defender and established chest-to-back control, threatening attacks from the back.",
            "visuals": [
                "Attacker is positioned behind the defender",
                "Chest-to-back alignment is present",
                "Hooks or seatbelt-style upper body control may be present",
            ],
        },
        "turtle": {
            "description": "One player is compact on elbows and knees while the opponent controls around the hips or upper body from a turtle exchange.",
            "visuals": [
                "Defender is balled up on knees and elbows",
                "Top player circles around the side or back",
                "Weight is directed forward to prevent recovery",
            ],
        },
        "closed_guard": {
            "description": "The bottom player has wrapped the legs around the opponent's waist to control distance and posture from guard.",
            "visuals": [
                "Bottom player's legs close around the torso",
                "Top player remains between the legs",
                "Distance and posture are controlled from the bottom",
            ],
        },
        "open_guard": {
            "description": "The bottom player is controlling distance with active legs and grips without a fully closed guard configuration.",
            "visuals": [
                "Legs frame or hook against the opponent",
                "Distance is managed from the bottom",
                "Guard remains open rather than locked closed",
            ],
        },
        "half_guard": {
            "description": "The bottom player traps one of the top player's legs, creating a half guard entanglement and limiting full control from top.",
            "visuals": [
                "One top leg is trapped between the bottom player's legs",
                "Top player applies pressure to free the knee line",
                "Bottom player uses frames or underhooks to recover position",
            ],
        },
        "50/50_guard": {
            "description": "Both players are engaged in a mirrored leg entanglement where each controls one of the other's legs from a 50/50 guard configuration.",
            "visuals": [
                "Both players' legs are intertwined symmetrically",
                "Neither side has fully passed the legs",
                "Control is built through leg entanglement rather than chest pins",
            ],
        },
        "standing": {
            "description": "Both players are upright in a standing or neutral grappling phase before a clear ground position is established.",
            "visuals": [
                "Both players remain on their feet",
                "No stable ground pin is established",
                "Hand fighting or clinch engagement may be present",
            ],
        },
        "standing_clinch": {
            "description": "Both players are standing and connected through upper-body ties or grips, competing for balance, head position, and takedown entries.",
            "visuals": [
                "Both players remain standing",
                "Upper-body grips or ties connect the athletes",
                "Head position and balance battle are visible",
            ],
        },
    },
    "SUBMISSION": {
        "kimura": {
            "description": "The attacker isolates the arm with a figure-four grip and bends the shoulder behind the opponent's back to attack the shoulder lock.",
            "visuals": [
                "Figure-four grip controls the wrist and forearm",
                "Elbow is isolated away from the torso",
                "Shoulder rotation is created behind the back line",
            ],
        },
        "armbar": {
            "description": "The attacker isolates the arm and extends the hips to create hyperextension pressure against the elbow joint.",
            "visuals": [
                "Arm is separated and controlled from wrist to elbow",
                "Hips align above or near the shoulder line",
                "Legs control the head or shoulder while extension is applied",
            ],
        },
        "armbar_from_mount": {
            "description": "The attacker transitions from mount to isolate the arm and extend through the elbow for a mounted armbar finish.",
            "visuals": [
                "Top player attacks from a mounted configuration",
                "Arm is isolated as hips rise toward the shoulder line",
                "Legs begin to clear the head while controlling posture",
            ],
        },
        "triangle_choke": {
            "description": "The attacker traps the neck and one arm between the legs and locks the figure-four leg configuration to apply a triangle choke.",
            "visuals": [
                "One leg crosses the back of the neck",
                "Opposite leg locks behind the knee",
                "One arm remains trapped inside the leg triangle",
            ],
        },
        "rear_naked_choke": {
            "description": "The attacker attacks from back control by wrapping the arm under the chin and closing the choke around the neck.",
            "visuals": [
                "Forearm threads under the chin",
                "Support hand connects behind the head or bicep",
                "Chest stays aligned behind the defender",
            ],
        },
        "guillotine": {
            "description": "The attacker controls the head and neck from the front and lifts or compresses to apply a guillotine choke.",
            "visuals": [
                "Head is trapped under the attacker's arm",
                "Hands connect around the neck or chin line",
                "Upward lift or crunching pressure is applied",
            ],
        },
        "lapel_choke": {
            "description": "The attacker feeds and tightens the lapel to create a choking structure around the neck using gi grips.",
            "visuals": [
                "A deep lapel grip is established",
                "Cloth is threaded across the neck line",
                "Upper body pressure tightens the choke",
            ],
        },
        "heel_hook": {
            "description": "The attacker entangles the leg, controls the heel, and applies rotational pressure to threaten the knee and ankle.",
            "visuals": [
                "Leg entanglement traps the opponent's hip line",
                "Heel is captured with a tight grip",
                "Rotational pressure targets the lower limb",
            ],
        },
    },
    "TRANSITION": {
        "guard_pass_to_mount": {
            "description": "The top player clears the guard and advances to a mounted position, improving control from the top.",
            "visuals": [
                "Leg line is cleared from top position",
                "Top player advances beyond the knees",
                "Hips settle into mount over the torso",
            ],
        },
        "guard_pass_to_side_control": {
            "description": "The top player passes beyond the legs and settles into side control from a dominant angle.",
            "visuals": [
                "Top player moves beyond the knee line",
                "Chest turns perpendicular to the torso",
                "Bottom player loses guard retention frames",
            ],
        },
        "sweep_/_reversal": {
            "description": "Control changes as the player underneath elevates, off-balances, or reverses the exchange to come on top.",
            "visuals": [
                "Bottom player creates off-balance or forward loading",
                "Top player's base is disrupted",
                "The exchange ends with top control changing hands",
            ],
        },
        "takedown": {
            "description": "The exchange moves from standing to the mat through off-balancing, penetration, or upper-body control that forces the opponent down.",
            "visuals": [
                "The action starts from a standing phase",
                "Balance is broken through driving or reaping mechanics",
                "The sequence ends with a grounded control outcome",
            ],
        },
        "grip_transition": {
            "description": "The athlete changes grips to improve control or unlock the next attacking phase of the sequence.",
            "visuals": [
                "One grip is released and another is established",
                "Hand placement changes the control structure",
                "The new grip clearly prepares a follow-up attack",
            ],
        },
        "forward_roll": {
            "description": "The attacker uses a forward rolling motion to maintain connection and improve positional control during the transition.",
            "visuals": [
                "Forward inversion or rolling action is visible",
                "Grip connection is maintained through the roll",
                "The movement ends in improved control or finishing alignment",
            ],
        },
        "half_guard_sweep": {
            "description": "The bottom player uses half guard leverage to off-balance the top player and reverse to top control.",
            "visuals": [
                "Half guard entanglement traps one leg",
                "Hook and upper-body connection load the opponent forward",
                "The bottom player comes up to finish on top",
            ],
        },
        "lateral_drop": {
            "description": "The attacker steps across from the clinch, loads the opponent, and drops to the hip to complete a lateral drop takedown.",
            "visuals": [
                "Step-across entry from upper-body control",
                "Opponent's weight is loaded across the attacker's hip line",
                "The attacker drops to rotate the opponent to the mat",
            ],
        },
        "judo_throw": {
            "description": "The attacker uses kuzushi, directional turning, and hip or leg engagement to project the opponent to the mat in a throwing exchange.",
            "visuals": [
                "Off-balancing precedes the throw",
                "Upper-body grips direct the opponent's posture",
                "Hip turn or reap projects the opponent downward",
            ],
        },
    },
}


def get_detection_details(category: str, label: str, *, inferred: bool = False) -> dict[str, object]:
    normalized_category = (category or "POSITION").upper()
    normalized_label = (label or "").strip().lower().replace(" ", "_")
    entry = DESCRIPTION_CATALOG.get(normalized_category, {}).get(normalized_label)

    if entry is None:
        readable = humanize_label(normalized_label)
        if inferred:
            return {
                "description": f"Positional context inferred for {readable} based on the dominant attacking mechanics in the sequence.",
                "visuals": [],
            }
        return {
            "description": f"{readable} identified by the local BJJ analysis pipeline.",
            "visuals": [],
        }

    if inferred:
        return {
            "description": f"Positional context inferred for {humanize_label(normalized_label)} based on the dominant attacking mechanics in the sequence.",
            "visuals": entry.get("visuals", []),
        }

    return {
        "description": str(entry["description"]),
        "visuals": list(entry.get("visuals", [])),
    }
