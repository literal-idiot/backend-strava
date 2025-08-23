from app import db
from models import Seed, IntensityLevel
from datetime import time

def calculate_coins_for_run(distance_km, intensity):
    """Calculate coins earned for a run based on distance and intensity"""
    # Base coins: 10 coins per km
    base_coins = int(distance_km * 10)
    
    # Intensity multipliers
    intensity_multipliers = {
        IntensityLevel.LOW: 1.0,
        IntensityLevel.MODERATE: 1.2,
        IntensityLevel.HIGH: 1.5,
        IntensityLevel.EXTREME: 2.0
    }
    
    multiplier = intensity_multipliers.get(intensity, 1.0)
    total_coins = int(base_coins * multiplier)
    
    # Bonus for longer runs
    if distance_km >= 10:
        total_coins += 50  # Bonus for 10K+
    if distance_km >= 21.1:
        total_coins += 100  # Bonus for half marathon+
    if distance_km >= 42.2:
        total_coins += 200  # Bonus for marathon+
    
    return total_coins

def create_default_seeds():
    """Create default seeds if they don't exist"""
    default_seeds = [
        {
            'name': 'Sunflower',
            'description': 'A practical flower. Grows predictably upward, as one does when chasing sunlight. Features a sensible spiral seed arrangement',
            'cost_coins': 50,
            'growth_requirements': {
                'preferred_intensity': 'moderate'
            },
            'rarity': 'common',
            'plant_type': 'endurance'
        },
        {
            'name': 'Orchid',
            'description': 'A needy flower. Attractive but needs a lot of maintenence. Reminds me of a certain someone...',
            'cost_coins': 75,
            'growth_requirements': {
                'preferred_intensity': 'high'
            },
            'rarity': 'common',
            'plant_type': 'effort'
        },
        {
            'name': 'Alpenrose',
            'description': 'A flower too stubborn to grow at sea level. Clings to mountains like I do for thick thighs',
            'cost_coins': 150,
            'growth_requirements': {
                'min_elevation_gain': 60
            },
            'rarity': 'rare',
            'plant_type': 'climb'
        },
        {
            'name': 'Peony',
            'description': 'A flower allergic to haste. Takes an eternity to bloom.',
            'cost_coins': 150,
            'growth_requirements': {
                'min_time': 60
            },
            'rarity': 'rare',
            'plant_type': 'duration'
        },
        {
            'name': 'Cosmos',
            'description': 'A light and airy flower that blooms hella quick. Gotta go fast.',
            'cost_coins': 200,
            'growth_requirements': {
                'min_pace_min_per_km': 3
            },
            'rarity': 'rare',
            'plant_type': 'speed'
        },
        {
            'name': 'Zinnia',
            'description': 'A flower that demands your attention, a perfect symbol for Strava clout.',
            'cost_coins': 500,
            'growth_requirements': {
                'min_kudos_count': 20
            },
            'rarity': 'epic',
            'plant_type': 'popularity'
        },
    ]
    
    for seed_data in default_seeds:
        existing_seed = Seed.query.filter_by(name=seed_data['name']).first()
        if not existing_seed:
            seed = Seed(**seed_data)
            db.session.add(seed)

'''
Future flower ideas
    - Queen of the Night: elapsed time

        {
            'name': 'Morning Glory',
            'description': 'I needed to give myself a reason to wake up early. Only for the legends that show up for morning practice.',
            'cost_coins': 1000,
            'growth_requirements': {
                'start_time': time(6, 0),
                'end_time': time(9,0),
            },
            'rarity': 'legendary',
            'plant_type': 'timing'
        }

'''