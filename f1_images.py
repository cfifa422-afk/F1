from typing import Dict, Optional

# ==================== DRIVER IMAGES ====================
# Sourced from Wikimedia Commons (free/open license)

DRIVER_IMAGES: Dict[str, str] = {
    # Current Grid
    "HAM": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Prime_Minister_Keir_Starmer_meets_Sir_Lewis_Hamilton_%2854566928382%29_%28cropped%29.jpg/1200px-Prime_Minister_Keir_Starmer_meets_Sir_Lewis_Hamilton_%2854566928382%29_%28cropped%29.jpg",
    "VER": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3973_by_Stepro_%28medium_crop%29.jpg/1200px-2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3973_by_Stepro_%28medium_crop%29.jpg",
    "NOR": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3968_by_Stepro_%28cropped2%29.jpg/1200px-2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3968_by_Stepro_%28cropped2%29.jpg",
    "LEC": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3978_by_Stepro_%28cropped2%29.jpg/1200px-2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3978_by_Stepro_%28cropped2%29.jpg",
    "RUS": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7f/KingsLeonSilverstne040724_%2828_of_112%29_%2853838006028%29_%28cropped%29.jpg/1200px-KingsLeonSilverstne040724_%2828_of_112%29_%2853838006028%29_%28cropped%29.jpg",
    "SAI": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/Formula1Gabelhofen2022_%2804%29_%28cropped2%29.jpg/1200px-Formula1Gabelhofen2022_%2804%29_%28cropped2%29.jpg",
    "ALO": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/Alonso-68_%2824710447098%29.jpg/1200px-Alonso-68_%2824710447098%29.jpg",
    "PIA": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/2026_Chinese_GP_-_Oscar_Piastri_%28cropped%29_%28cropped%29.jpg/1200px-2026_Chinese_GP_-_Oscar_Piastri_%28cropped%29_%28cropped%29.jpg",
    "TSU": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Yuki_Tsunoda_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A8096%29.jpg/1200px-Yuki_Tsunoda_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A8096%29.jpg",
    "GAS": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fd/2022_French_Grand_Prix_%2852279065728%29_%28midcrop%29.png/1200px-2022_French_Grand_Prix_%2852279065728%29_%28midcrop%29.png",
    "OCO": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Esteban_Ocon_2024_Suzuka_%28cropped%29.jpg/1200px-Esteban_Ocon_2024_Suzuka_%28cropped%29.jpg",
    "BOT": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Valtteri_Bottas_at_the_2026_Adelaide_Motorsport_Festival_%28028A7556%29.jpg/1200px-Valtteri_Bottas_at_the_2026_Adelaide_Motorsport_Festival_%28028A7556%29.jpg",
    "MAG": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Kevin_Magnussen%2C_2019_Formula_One_Tests_Barcelona_%28cropped%29.jpg/1200px-Kevin_Magnussen%2C_2019_Formula_One_Tests_Barcelona_%28cropped%29.jpg",
    "STR": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/2025_Japan_GP_-_Aston_Martin_-_Lance_Stroll_-_Fanzone_Stage_%28cropped%29.jpg/1200px-2025_Japan_GP_-_Aston_Martin_-_Lance_Stroll_-_Fanzone_Stage_%28cropped%29.jpg",
    "ALB": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Alex_Albon_%28cropped%29.jpg/1200px-Alex_Albon_%28cropped%29.jpg",
    "HUL": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/2019_Formula_One_tests_Barcelona%2C_Hulkenberg_%2840287128313%29.jpg/1200px-2019_Formula_One_tests_Barcelona%2C_Hulkenberg_%2840287128313%29.jpg",
    "ZHO": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Zhou_Guanyu_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A7999%29.jpg/1200px-Zhou_Guanyu_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A7999%29.jpg",
    "SAR": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/Logan_Sargeant_NYC_%28cropped%29.jpg/1200px-Logan_Sargeant_NYC_%28cropped%29.jpg",
    "PER": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/2021_US_GP_driver_parade_%28cropped2%29.jpg/1200px-2021_US_GP_driver_parade_%28cropped2%29.jpg",
    # Retired Legends
    "SEN": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Ayrton_Senna_9_%28cropped%29.jpg/1200px-Ayrton_Senna_9_%28cropped%29.jpg",
    "MSC": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/A%C3%A9cio_Neves%2C_Michael_Schumacher_e_Didi_%28Cropped%29.jpg/1200px-A%C3%A9cio_Neves%2C_Michael_Schumacher_e_Didi_%28Cropped%29.jpg",
    "PRO": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Festival_automobile_international_2015_-_Photocall_-_065_%28cropped3%29.jpg/1200px-Festival_automobile_international_2015_-_Photocall_-_065_%28cropped3%29.jpg",
    "NIK": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/Lauda_at_1982_Dutch_Grand_Prix.jpg/1200px-Lauda_at_1982_Dutch_Grand_Prix.jpg",
    "FAN": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Fangio_in_1955_%28cropped%29.jpg/1200px-Fangio_in_1955_%28cropped%29.jpg",
    "CLK": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Jim_Clark_in_1963_%28cropped%29.JPG/1200px-Jim_Clark_in_1963_%28cropped%29.JPG",
    "MAN": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Nigel_Mansell_-_Mexican_Grand_Prix_01_%28cropped%29.jpeg/1200px-Nigel_Mansell_-_Mexican_Grand_Prix_01_%28cropped%29.jpeg",
    "HIL": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Damon_Hill_at_the_Atlassian_Williams_Racing_Fan_Zone_of_2026_%28028A8241%29.jpg/1200px-Damon_Hill_at_the_Atlassian_Williams_Racing_Fan_Zone_of_2026_%28028A8241%29.jpg",
    "ROS": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Nico_Rosberg_2016.jpg/1200px-Nico_Rosberg_2016.jpg",
    "BUT": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Jenson_Button_2024_WEC_Fuji.jpg/1200px-Jenson_Button_2024_WEC_Fuji.jpg",
    "RAI": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/ff/F12019_Schloss_Gabelhofen_%2822%29_%28cropped%29.jpg/1200px-F12019_Schloss_Gabelhofen_%2822%29_%28cropped%29.jpg",
}

# ==================== CAR IMAGES ====================

CAR_IMAGES: Dict[str, str] = {
    "Red Bull RB19": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/79/FIA_F1_Austria_2023_Nr._1_%281%29.jpg/1200px-FIA_F1_Austria_2023_Nr._1_%281%29.jpg",
    "Red Bull RB18": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/79/FIA_F1_Austria_2023_Nr._1_%281%29.jpg/1200px-FIA_F1_Austria_2023_Nr._1_%281%29.jpg",
    "Ferrari SF-23": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/FIA_F1_Austria_2023_Nr._55_%281%29.jpg/1200px-FIA_F1_Austria_2023_Nr._55_%281%29.jpg",
    "Ferrari SF-23+": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/FIA_F1_Austria_2023_Nr._55_%281%29.jpg/1200px-FIA_F1_Austria_2023_Nr._55_%281%29.jpg",
    "Ferrari F1-75": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Charles_Leclerc_2022.jpg/1200px-Charles_Leclerc_2022.jpg",
    "Ferrari F1-75+": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Charles_Leclerc_2022.jpg/1200px-Charles_Leclerc_2022.jpg",
    "McLaren MCL60": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/FIA_F1_Austria_2023_Nr._4_%282%29.jpg/1200px-FIA_F1_Austria_2023_Nr._4_%282%29.jpg",
    "McLaren MCL60S": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/FIA_F1_Austria_2023_Nr._4_%282%29.jpg/1200px-FIA_F1_Austria_2023_Nr._4_%282%29.jpg",
    "McLaren MCL36": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Lando_Norris_drives_the_McLaren_MCL36_during_the_2022_British_Grand_Prix..jpg/1200px-Lando_Norris_drives_the_McLaren_MCL36_during_the_2022_British_Grand_Prix..jpg",
    "Aston Martin AMR23": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/FIA_F1_Austria_2023_Nr._14_%281%29.jpg/1200px-FIA_F1_Austria_2023_Nr._14_%281%29.jpg",
    "Aston Martin AMR22": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/FIA_F1_Austria_2023_Nr._14_%281%29.jpg/1200px-FIA_F1_Austria_2023_Nr._14_%281%29.jpg",
    "Alpine A523": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/FIA_F1_Austria_2023_Nr._10_%282%29_%28cropped%29.jpg/1200px-FIA_F1_Austria_2023_Nr._10_%282%29_%28cropped%29.jpg",
    "Alpine A522": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/FIA_F1_Austria_2023_Nr._10_%282%29_%28cropped%29.jpg/1200px-FIA_F1_Austria_2023_Nr._10_%282%29_%28cropped%29.jpg",
    "Mercedes AMG W14": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/FIA_F1_Austria_2023_Nr._44_%282%29.jpg/1200px-FIA_F1_Austria_2023_Nr._44_%282%29.jpg",
    "Mercedes AMG W13": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/FIA_F1_Austria_2023_Nr._44_%282%29.jpg/1200px-FIA_F1_Austria_2023_Nr._44_%282%29.jpg",
    "Williams FW45": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/FIA_F1_Austria_2023_Nr._23_%282%29.jpg/1200px-FIA_F1_Austria_2023_Nr._23_%282%29.jpg",
    "Williams FW44": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/FIA_F1_Austria_2022_Nr._23_Albon.jpg/1200px-FIA_F1_Austria_2022_Nr._23_Albon.jpg",
    "AlphaTauri AT04": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/FIA_F1_Austria_2023_Nr._21_%282%29.jpg/1200px-FIA_F1_Austria_2023_Nr._21_%282%29.jpg",
    "Haas VF-23": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/FIA_F1_Austria_2023_Nr._27_%282%29.jpg/1200px-FIA_F1_Austria_2023_Nr._27_%282%29.jpg",
    "Alfa Romeo C43": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/FIA_F1_Austria_2023_Nr._24_%282%29.jpg/1200px-FIA_F1_Austria_2023_Nr._24_%282%29.jpg",
}

# ==================== LOOKUP HELPERS ====================

def get_driver_image(code: str) -> Optional[str]:
    return DRIVER_IMAGES.get(code)


def get_car_image(name: str) -> Optional[str]:
    if name in CAR_IMAGES:
        return CAR_IMAGES[name]
    name_lower = name.lower()
    for car_name, url in CAR_IMAGES.items():
        if car_name.lower() in name_lower or name_lower in car_name.lower():
            return url
    return None


def get_card_image(card: dict) -> Optional[str]:
    """Return an image URL for a card dict (driver or car)."""
    if card["type"] == "driver":
        return get_driver_image(card.get("code", ""))
    else:
        return get_car_image(card.get("name", ""))


# Total images available
TOTAL_IMAGES = len(DRIVER_IMAGES) + len(set(CAR_IMAGES.values()))
