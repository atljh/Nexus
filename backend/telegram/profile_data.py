"""Random profile generation data and utilities."""

import random
from typing import Optional

MALE_NAMES_EN = [
    "James", "John", "Robert", "Michael", "David", "William", "Richard", "Joseph",
    "Thomas", "Daniel", "Matthew", "Anthony", "Mark", "Steven", "Andrew", "Joshua",
    "Kevin", "Brian", "George", "Edward", "Ryan", "Timothy", "Jason", "Jeffrey",
    "Nathan", "Patrick", "Dennis", "Jerry", "Tyler", "Aaron", "Henry", "Douglas",
    "Peter", "Adam", "Scott", "Frank", "Benjamin", "Samuel", "Raymond", "Gregory",
    "Jack", "Alexander", "Dylan", "Luke", "Ethan", "Oliver", "Leo", "Max",
]

FEMALE_NAMES_EN = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan",
    "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra",
    "Ashley", "Emily", "Donna", "Michelle", "Dorothy", "Carol", "Amanda", "Melissa",
    "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Kathleen",
    "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma", "Nicole",
    "Helen", "Samantha", "Katherine", "Christine", "Debra", "Rachel", "Carolyn",
    "Janet", "Catherine", "Maria", "Heather", "Diane", "Ruth", "Julie", "Olivia",
    "Joyce", "Virginia", "Victoria", "Kelly", "Lauren", "Christina", "Joan", "Evelyn",
    "Sophia", "Chloe", "Mia", "Lily", "Grace", "Zoe", "Hannah", "Natalie",
]

MALE_NAMES_UA = [
    "Олександр", "Максим", "Артем", "Дмитро", "Андрій", "Іван", "Михайло",
    "Владислав", "Даніл", "Кирило", "Богдан", "Нікіта", "Єгор", "Роман",
    "Тимофій", "Матвій", "Ілля", "Арсеній", "Назар", "Денис", "Олег",
    "Сергій", "Тарас", "Вадим", "Юрій", "Павло", "Віталій", "Ярослав",
]

FEMALE_NAMES_UA = [
    "Анастасія", "Марія", "Софія", "Анна", "Вікторія", "Дарія", "Олександра",
    "Поліна", "Єлизавета", "Катерина", "Ірина", "Аліна", "Ксенія", "Ольга",
    "Тетяна", "Наталія", "Юлія", "Діана", "Валерія", "Карина", "Злата",
    "Мілана", "Еміліа", "Ангеліна", "Кристина", "Маргарита", "Вероніка",
]

LAST_NAMES_EN = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas", "Moore", "Jackson",
    "Martin", "Lee", "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Hill",
    "Green", "Adams", "Baker", "Nelson", "Carter", "Mitchell", "Roberts", "Turner",
    "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart",
]

LAST_NAMES_UA_MALE = [
    "Шевченко", "Бондаренко", "Ткаченко", "Коваленко", "Бойко", "Кравченко",
    "Олійник", "Мельник", "Лисенко", "Марченко", "Поліщук", "Шевчук",
    "Козак", "Гончаренко", "Карпенко", "Василенко", "Романенко", "Петренко",
    "Кузьменко", "Мороз", "Литвиненко", "Савченко", "Руденко", "Тимченко",
]

LAST_NAMES_UA_FEMALE = [
    "Шевченко", "Бондаренко", "Ткаченко", "Коваленко", "Бойко", "Кравченко",
    "Олійник", "Мельник", "Лисенко", "Марченко", "Поліщук", "Шевчук",
    "Козак", "Гончаренко", "Карпенко", "Василенко", "Романенко", "Петренко",
]

BIOS_EN = [
    "just living life", "coffee enthusiast", "dog lover", "travel addict",
    "music is my therapy", "dreamer & doer", "fitness junkie",
    "photography lover", "foodie", "book worm", "nature lover",
    "tech geek", "art lover", "movie buff", "gamer",
    "wanderlust", "cat person", "sports fan", "pizza lover",
    "music & coffee", "exploring the world", "living my best life",
    "adventure seeker", "simple life", "work hard play hard",
    "love laugh live", "positive vibes only", "keep it real",
    "life is beautiful", "stay humble", "be kind",
]

BIOS_UA = [
    "просто живу", "люблю каву", "мандрівник", "музика - це життя",
    "фотографія", "люблю тварин", "спорт", "книголюб",
    "природа", "технології", "кіноман", "геймер",
    "мандри", "люблю котиків", "їжа", "мистецтво",
    "живу і насолоджуюсь", "просто я", "позитив", "усмішка",
]


def generate_random_profile(gender: Optional[str] = None, locale: str = "en") -> dict:
    """Generate random profile data."""
    if gender is None:
        gender = random.choice(["male", "female"])

    if locale == "ua":
        if gender == "male":
            first = random.choice(MALE_NAMES_UA)
            last = random.choice(LAST_NAMES_UA_MALE)
        else:
            first = random.choice(FEMALE_NAMES_UA)
            last = random.choice(LAST_NAMES_UA_FEMALE)
        bio = random.choice(BIOS_UA)
    else:
        if gender == "male":
            first = random.choice(MALE_NAMES_EN)
        else:
            first = random.choice(FEMALE_NAMES_EN)
        last = random.choice(LAST_NAMES_EN)
        bio = random.choice(BIOS_EN)

    # 30% chance to omit last name
    if random.random() < 0.3:
        last = ""

    # 40% chance to omit bio
    if random.random() < 0.4:
        bio = ""

    return {
        "first_name": first,
        "last_name": last,
        "bio": bio,
    }
