#!/usr/bin/env python3
# Test de génération des créneaux de 15 minutes

def generate_time_slots():
    """Test de génération des créneaux"""
    time_slots = []
    start_hour = 9
    start_minute = 0
    end_hour = 18
    end_minute = 15
    
    current_hour = start_hour
    current_minute = start_minute
    
    while current_hour < end_hour or (current_hour == end_hour and current_minute <= end_minute):
        time_slot = f"{current_hour}h{current_minute:02d}"
        time_slots.append(time_slot)
        
        # Incrémenter de 15 minutes
        current_minute += 15
        if current_minute >= 60:
            current_minute = 0
            current_hour += 1
    
    return time_slots

if __name__ == "__main__":
    slots = generate_time_slots()
    print(f"Total créneaux: {len(slots)}")
    print(f"Créneaux 9h: {[slot for slot in slots if slot.startswith('9h')]}")
    print(f"Créneaux 10h: {[slot for slot in slots if slot.startswith('10h')]}")
    print(f"Premiers 20: {slots[:20]}")
    print(f"Tous: {slots}")