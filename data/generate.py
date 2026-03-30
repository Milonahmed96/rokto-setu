"""
data/generate.py
----------------
Generates 500 synthetic Bangladeshi blood donor profiles using Claude API.
Profiles are statistically distributed to match real Bangladesh demographics.

Usage:
    python -m data.generate
    python -m data.generate --count 100 --output data/synthetic/donors.json
"""

import argparse
import asyncio
import json
import hashlib
import random
from pathlib import Path
from datetime import datetime, timedelta

import anthropic

# ── Blood group distribution — matches Bangladesh population ──────────────────
BLOOD_GROUP_WEIGHTS = {
    "O+":  37,
    "A+":  28,
    "B+":  22,
    "AB+":  7,
    "O-":   2,
    "A-":   2,
    "B-":   1,
    "AB-":  1,
}

# ── Bangladesh districts with population weights ───────────────────────────────
DISTRICTS = [
    {"id": 1,  "name": "Dhaka",        "division_id": 1, "division": "Dhaka",      "weight": 20},
    {"id": 2,  "name": "Gazipur",      "division_id": 1, "division": "Dhaka",      "weight":  6},
    {"id": 3,  "name": "Narayanganj",  "division_id": 1, "division": "Dhaka",      "weight":  5},
    {"id": 4,  "name": "Narsingdi",    "division_id": 1, "division": "Dhaka",      "weight":  3},
    {"id": 5,  "name": "Manikganj",    "division_id": 1, "division": "Dhaka",      "weight":  2},
    {"id": 7,  "name": "Chittagong",   "division_id": 2, "division": "Chittagong", "weight": 12},
    {"id": 8,  "name": "Cox's Bazar",  "division_id": 2, "division": "Chittagong", "weight":  3},
    {"id": 9,  "name": "Sylhet",       "division_id": 3, "division": "Sylhet",     "weight":  5},
    {"id": 10, "name": "Sunamganj",    "division_id": 3, "division": "Sylhet",     "weight":  2},
    {"id": 11, "name": "Rajshahi",     "division_id": 4, "division": "Rajshahi",   "weight":  5},
    {"id": 12, "name": "Khulna",       "division_id": 5, "division": "Khulna",     "weight":  5},
    {"id": 13, "name": "Barisal",      "division_id": 6, "division": "Barisal",    "weight":  3},
    {"id": 14, "name": "Rangpur",      "division_id": 7, "division": "Rangpur",    "weight":  4},
    {"id": 15, "name": "Mymensingh",   "division_id": 8, "division": "Mymensingh", "weight":  4},
    {"id": 16, "name": "Bogura",       "division_id": 4, "division": "Rajshahi",   "weight":  3},
    {"id": 17, "name": "Comilla",      "division_id": 2, "division": "Chittagong", "weight":  4},
    {"id": 18, "name": "Jessore",      "division_id": 5, "division": "Khulna",     "weight":  3},
    {"id": 19, "name": "Dinajpur",     "division_id": 7, "division": "Rangpur",    "weight":  3},
    {"id": 20, "name": "Tangail",      "division_id": 1, "division": "Dhaka",      "weight":  3},
    {"id": 21, "name": "Noakhali",     "division_id": 2, "division": "Chittagong", "weight":  3},
]

UPAZILAS = {
    1:  ["Mirpur", "Gulshan", "Mohammadpur", "Uttara", "Demra", "Savar", "Dhanmondi", "Motijheel", "Wari", "Tejgaon"],
    2:  ["Gazipur Sadar", "Tongi", "Kaliakair", "Kapasia", "Sreepur"],
    3:  ["Narayanganj Sadar", "Sonargaon", "Araihazar", "Rupganj"],
    4:  ["Narsingdi Sadar", "Palash", "Shibpur", "Raipura"],
    5:  ["Manikganj Sadar", "Singair", "Shibalaya", "Saturia"],
    7:  ["Kotwali", "Pahartali", "Panchlaish", "Halishahar", "Chandgaon", "Double Mooring"],
    8:  ["Cox's Bazar Sadar", "Teknaf", "Ukhia", "Ramu"],
    9:  ["Sylhet Sadar", "Bianibazar", "Golapganj", "Osmani Nagar"],
    10: ["Sunamganj Sadar", "Chhatak", "Jagannathpur"],
    11: ["Rajshahi Sadar", "Boalia", "Motihar", "Paba"],
    12: ["Khulna Sadar", "Sonadanga", "Khalishpur", "Daulatpur"],
    13: ["Barisal Sadar", "Bakerganj", "Wazirpur"],
    14: ["Rangpur Sadar", "Mithapukur", "Gangachara"],
    15: ["Mymensingh Sadar", "Trishal", "Valuka", "Muktagacha"],
    16: ["Bogura Sadar", "Shibganj", "Gabtali"],
    17: ["Comilla Sadar", "Laksam", "Chandina"],
    18: ["Jessore Sadar", "Jhikargacha", "Chaugachha"],
    19: ["Dinajpur Sadar", "Birampur", "Chirirbandar"],
    20: ["Tangail Sadar", "Ghatail", "Kalihati"],
    21: ["Noakhali Sadar", "Begumganj", "Companiganj"],
}

NOTIFICATION_RANGES = ["UNION", "UPAZILA", "DISTRICT"]
NOTIFICATION_WEIGHTS = [10, 60, 30]

BADGES = ["none", "none", "none", "lifesaver", "lifesaver", "hero", "legend"]


def _weighted_choice(items: list, weights: list):
    return random.choices(items, weights=weights, k=1)[0]


def _random_district():
    weights = [d["weight"] for d in DISTRICTS]
    return _weighted_choice(DISTRICTS, weights)


def _random_blood_group():
    groups = list(BLOOD_GROUP_WEIGHTS.keys())
    weights = list(BLOOD_GROUP_WEIGHTS.values())
    return _weighted_choice(groups, weights)


def _random_phone():
    """Generate a realistic Bangladesh mobile number."""
    prefixes = ["013", "014", "015", "016", "017", "018", "019"]
    prefix = random.choice(prefixes)
    suffix = "".join([str(random.randint(0, 9)) for _ in range(8)])
    return f"{prefix}{suffix}"


def _hash_phone(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def _random_donation_history():
    """Generate realistic donation history."""
    total = random.choices(
        [0, 1, 2, 3, 4, 5, 8, 12, 20],
        weights=[20, 20, 15, 12, 10, 8, 7, 5, 3],
        k=1
    )[0]

    if total == 0:
        return {
            "total_donations": 0,
            "last_donated": None,
            "next_eligible_date": None,
            "is_active_donor": random.choice([True, True, False]),
            "badge": "none",
        }

    # Last donation between 91 days ago and 3 years ago
    days_ago = random.randint(91, 1095)
    last_donated = datetime.now() - timedelta(days=days_ago)
    next_eligible = last_donated + timedelta(days=90)
    is_eligible = next_eligible <= datetime.now()

    badge = "none"
    if total >= 20:
        badge = "legend"
    elif total >= 5:
        badge = "hero"
    elif total >= 1:
        badge = "lifesaver"

    return {
        "total_donations": total,
        "last_donated": last_donated.strftime("%Y-%m-%d"),
        "next_eligible_date": next_eligible.strftime("%Y-%m-%d"),
        "is_active_donor": is_eligible and random.choice([True, True, True, False]),
        "badge": badge,
    }


async def generate_names_batch(
    client: anthropic.AsyncAnthropic,
    count: int,
    batch_num: int,
) -> list[dict]:
    """
    Use Claude to generate realistic Bangladeshi donor profiles.
    Returns a list of dicts with name and anonymous_handle fields.
    """
    print(f"  Generating batch {batch_num} — {count} names via Claude API...")

    prompt = f"""Generate {count} realistic Bangladeshi people for a blood donor database.
Return ONLY a JSON array, no other text, no markdown.

Each object must have exactly these fields:
- "name_en": full name in English (realistic Bangladeshi Muslim, Hindu, or Christian name)
- "name_bn": full name in Bengali script
- "gender": "male" or "female"
- "anonymous_handle": a privacy-safe handle like "Donor_Mirpur_42" or "Helper_Dhaka_07" (never use real name)
- "age": integer between 18 and 55

Mix of Muslim names (~88%), Hindu names (~10%), Christian names (~2%).
Mix of male (~65%) and female (~35%) donors.
Make names genuinely diverse — not all the same surname.

Return exactly {count} objects in a JSON array."""

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


async def generate_donors(count: int = 500) -> list[dict]:
    """Generate `count` synthetic donor profiles."""
    client = anthropic.AsyncAnthropic()

    # Generate names in batches of 50 to stay within token limits
    batch_size = 50
    all_names = []
    total_batches = (count + batch_size - 1) // batch_size

    print(f"\nGenerating {count} donor profiles in {total_batches} batches...")

    for i in range(total_batches):
        this_batch = min(batch_size, count - len(all_names))
        names = await generate_names_batch(client, this_batch, i + 1)
        all_names.extend(names)
        print(f"  Batch {i+1}/{total_batches} complete — {len(all_names)} names so far")

    print(f"\nAssembling full donor profiles...")

    donors = []
    used_phones = set()

    for i, name_data in enumerate(all_names):
        # Unique phone
        phone = _random_phone()
        while phone in used_phones:
            phone = _random_phone()
        used_phones.add(phone)

        district = _random_district()
        upazila_list = UPAZILAS.get(district["id"], ["Sadar"])
        upazila = random.choice(upazila_list)
        union_id = district["id"] * 100 + random.randint(1, 10)

        history = _random_donation_history()
        blood_group = _random_blood_group()
        notif_range = _weighted_choice(
            NOTIFICATION_RANGES, NOTIFICATION_WEIGHTS
        )

        donor = {
            "donor_index":         i + 1,
            "phone":               phone,
            "phone_hash":          _hash_phone(phone),
            "name_en":             name_data.get("name_en", f"Donor {i+1}"),
            "name_bn":             name_data.get("name_bn", ""),
            "gender":              name_data.get("gender", "male"),
            "anonymous_handle":    name_data.get("anonymous_handle", f"Donor_{i+1:03d}"),
            "age":                 name_data.get("age", random.randint(18, 55)),
            "blood_group":         blood_group,
            "division_id":         district["division_id"],
            "division_name":       district["division"],
            "district_id":         district["id"],
            "district_name":       district["name"],
            "upazila_id":          district["id"] * 10 + random.randint(1, 8),
            "upazila_name":        upazila,
            "union_id":            union_id,
            "union_name":          f"{upazila} Union {union_id % 10 + 1}",
            "notification_range":  notif_range,
            "total_donations":     history["total_donations"],
            "last_donated":        history["last_donated"],
            "next_eligible_date":  history["next_eligible_date"],
            "is_active_donor":     history["is_active_donor"],
            "badge":               history["badge"],
            "response_rate":       round(random.uniform(0.4, 0.95), 2),
            "created_at":          (
                datetime.now() - timedelta(days=random.randint(30, 730))
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        donors.append(donor)

    return donors


async def main():
    parser = argparse.ArgumentParser(description="Generate synthetic donor profiles")
    parser.add_argument("--count",  type=int, default=500, help="Number of donors")
    parser.add_argument("--output", type=str,
                        default="data/synthetic/donors.json",
                        help="Output file path")
    args = parser.parse_args()

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    donors = await generate_donors(args.count)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(donors, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Generated {len(donors)} donor profiles")
    print(f"✓ Saved to {output_path}")

    # Print summary stats
    blood_counts = {}
    for d in donors:
        bg = d["blood_group"]
        blood_counts[bg] = blood_counts.get(bg, 0) + 1

    print("\nBlood group distribution:")
    for bg, count in sorted(blood_counts.items()):
        bar = "█" * (count // 5)
        print(f"  {bg:4s}  {count:3d}  {bar}")

    active = sum(1 for d in donors if d["is_active_donor"])
    print(f"\nActive donors:   {active}/{len(donors)}")
    print(f"Total donations: {sum(d['total_donations'] for d in donors)}")


if __name__ == "__main__":
    asyncio.run(main())