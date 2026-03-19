# Centre-point coordinates for each ward in Mira Bhayandar
# Used when a tanker has no live GPS — we use its assigned ward location
WARD_COORDS = {
    "A": {"lat": 19.2952, "lng": 72.8544},  # Mira Road East
    "B": {"lat": 19.2830, "lng": 72.8450},  # Mira Road West
    "C": {"lat": 19.2680, "lng": 72.8600},  # Bhayandar East
    "D": {"lat": 19.2600, "lng": 72.8400},  # Bhayandar West
    "E": {"lat": 19.3100, "lng": 72.8200},  # Uttan
}

# Booking address coordinates are not real GPS in Phase 3
# We use the ward centre as a stand-in until Phase 4 adds geocoding
def get_ward_coords(ward: str):
    return WARD_COORDS.get(ward, {"lat": 19.2952, "lng": 72.8544})