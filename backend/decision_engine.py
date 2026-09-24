from datetime import datetime


def decide_room_action(
    current_occupancy,
    expected_attendees,
    room_capacity,
    minutes_since_start,
    grace_period=10
):
    """
    Context-Aware Decision Engine for SmartRoom AI.

    Returns:
        KEEP
        WAIT
        RELEASE
        SUGGEST
    """

    # Safety check
    if room_capacity <= 0:
        return "RELEASE"

    # --------------------------------------------------
    # CASE 1: People are already inside the room
    # --------------------------------------------------

    if current_occupancy > 0:

        # Room is being used
        if current_occupancy <= room_capacity:
            return "KEEP"


    # --------------------------------------------------
    # CASE 2: Nobody is currently inside
    # --------------------------------------------------

    if current_occupancy == 0:

        # Meeting has just started.
        # Give attendees some time to arrive.
        if minutes_since_start < grace_period:
            return "WAIT"

        # Grace period has expired and nobody arrived.
        return "RELEASE"


    # --------------------------------------------------
    # CASE 3: Occupancy exceeds room capacity
    # --------------------------------------------------

    if current_occupancy > room_capacity:
        return "SUGGEST"


    # Default decision
    return "WAIT"


# --------------------------------------------------
# TEST THE ENGINE
# --------------------------------------------------

if __name__ == "__main__":

    print("SmartRoom AI - Decision Engine Test")
    print("=" * 45)

    result = decide_room_action(
        current_occupancy=5,
        expected_attendees=6,
        room_capacity=8,
        minutes_since_start=5
    )

    print("Decision:", result)