# scale_scenarios.py — 1000+ turn marathon scenario for scale ablation study.
# Created: 2026-03-11
# Generates a deterministic 1000-turn conversation that proves Soul Protocol's
# selective storage scales better than RAG at high turn counts. At 160 turns,
# RAG wins on recall (stores everything). At 1000+ turns, BM25/vector search
# gets noisier while Soul's lean corpus stays precise.
#
# Structure:
#   - 35 important facts planted every ~25-30 turns across the full 1000 turns
#   - Fact categories: life events, names, dates, preferences, emotional moments
#   - "Callback" facts planted early (turns 10-50), never mentioned again
#   - "Buried" facts surrounded by 50+ turns of filler on both sides
#   - 40 test points at the end querying ALL planted facts
#   - Remaining ~960 turns are varied filler (weather, small talk, topics, daily updates)

from __future__ import annotations

import random

from .scenarios import LongHorizonScenario, TestPoint, _filler_turns


# ---------------------------------------------------------------------------
# Extended filler banks for 1000-turn scale (more variety to avoid repetition)
# ---------------------------------------------------------------------------

_DAILY_UPDATES = [
    ("Had cereal for breakfast today.", "A classic start to the day."),
    ("Took the bus to work this morning.", "Public transit keeps things simple."),
    ("My alarm didn't go off today.", "That's always a stressful way to wake up."),
    ("I packed my lunch for the first time in weeks.", "Homemade lunches save money too."),
    ("Went to bed early last night.", "Getting enough sleep makes a big difference."),
    ("I washed my car this weekend.", "A clean car feels so satisfying."),
    ("The elevator was broken again at work.", "That must be annoying, especially with stairs."),
    ("I tried a new brand of coffee.", "How did it compare to your usual?"),
    ("My neighbor moved out yesterday.", "Changes in the building can feel weird."),
    ("I organized my closet this morning.", "A fresh closet always feels productive."),
    ("Had a dentist appointment today.", "Hope everything checked out okay."),
    ("I dropped my phone and cracked the screen.", "Oh no, that's always frustrating."),
    ("Went to the post office to mail a package.", "Post office trips are never quick."),
    ("My wifi went out for an hour.", "That's always inconvenient."),
    ("I skipped lunch today, too busy.", "Don't forget to eat — fuel matters."),
    ("Got a parking ticket this morning.", "That's a rough start to the day."),
    ("I cleaned the bathroom after work.", "Not glamorous but it had to be done."),
    ("Made pasta for dinner tonight.", "Simple dinners can be the best."),
    ("My cat knocked a glass off the counter.", "Classic cat behavior."),
    ("I forgot to charge my laptop last night.", "Starting the day on low battery is stressful."),
    ("Took a long shower after the gym.", "A hot shower after a workout is the best feeling."),
    ("I ironed my shirt for tomorrow.", "Preparation is key."),
    ("Had a video call with my parents.", "Family calls are always nice."),
    ("I refilled my water bottle three times today.", "Staying hydrated is key."),
    ("My headphones stopped working.", "Time for an upgrade maybe?"),
    ("I rearranged the furniture in the living room.", "A change of scenery at home can be refreshing."),
    ("I microwaved leftovers for lunch.", "Leftovers are the ultimate convenience."),
    ("Took the dog for an extra-long walk.", "Sounds like a good reset for both of you."),
    ("I fixed a squeaky door hinge.", "Small home repairs feel so satisfying."),
    ("Had to wait 20 minutes for an Uber.", "Surge pricing or just bad timing?"),
]

_MUNDANE_TOPICS = [
    ("I think I need new running shoes.", "Good shoes make a big difference."),
    ("The grocery store was out of my favorite yogurt.", "That's always disappointing."),
    ("I cleaned out my email inbox.", "Inbox zero is a great feeling."),
    ("My coworker keeps microwaving fish at lunch.", "That's a classic office complaint."),
    ("I started using a new toothpaste brand.", "Any noticeable difference?"),
    ("The traffic light near my house was broken.", "Hope they fix it before someone gets hurt."),
    ("I bought new socks.", "New socks are an underrated pleasure."),
    ("My phone updated overnight and moved all my apps.", "Automatic updates can be so disruptive."),
    ("I tried oat milk in my coffee.", "Oat milk has become so popular. Did you like it?"),
    ("My printer ran out of ink.", "Printer ink is weirdly expensive."),
    ("I found a spider in the bathroom.", "Spiders can be unsettling."),
    ("Had to replace a lightbulb today.", "At least it's a quick fix."),
    ("I subscribed to a new streaming service.", "There are so many options now."),
    ("My lease renewal came in the mail.", "Any changes to the terms?"),
    ("I tried a new brand of shampoo.", "Hair products can be hit or miss."),
    ("The vending machine ate my dollar.", "That's always infuriating."),
    ("I looked up recipes for smoothies.", "Smoothies are a great way to pack in nutrients."),
    ("My phone battery barely lasted the day.", "Might be time for a battery check."),
    ("I flossed for the first time in a while.", "Better late than never!"),
    ("The line at the pharmacy was so long.", "Pharmacy waits can test your patience."),
    ("I switched to a different email app.", "Finding the right email app matters."),
    ("My coworker brought in donuts.", "Free donuts are always a win."),
    ("I need to schedule an oil change.", "Regular maintenance keeps things running smoothly."),
    ("I noticed a new restaurant opening nearby.", "Exciting — always fun to try new places."),
    ("My recycling bin was overflowing.", "Time for a trip to the recycling center."),
    ("I reorganized my bookshelf.", "A neat bookshelf is oddly satisfying."),
    ("Had to call customer support for my internet.", "Customer support calls can be a real test of patience."),
    ("I cleaned my keyboard with compressed air.", "The amount of dust in keyboards is shocking."),
    ("My coworker's birthday is next week.", "Are you planning anything?"),
    ("I changed my desktop wallpaper.", "A small change that can freshen things up."),
]

_EXTENDED_TOPICS = [
    ("I read about a new planet they discovered.", "Space discoveries are always fascinating."),
    ("Thinking about learning to bake bread.", "Bread baking can be really therapeutic."),
    ("I watched a movie about time travel.", "Time travel movies always make you think."),
    ("My friend sent me a funny video.", "Sharing laughs with friends is the best."),
    ("I started a crossword puzzle book.", "Crosswords are great for the brain."),
    ("Looked into getting a library card.", "Libraries are such an underused resource."),
    ("I tried meditation for 10 minutes.", "Even short meditation sessions can help."),
    ("Thinking about repainting the kitchen.", "What color are you considering?"),
    ("I heard a good song on the radio.", "Music can really make your day better."),
    ("Thought about picking up photography.", "Photography is a wonderful creative outlet."),
    ("I read about coral reef conservation.", "Ocean conservation is so important."),
    ("Tried a new type of herbal tea.", "Herbal teas can be really soothing."),
    ("I organized my photo albums.", "Looking through old photos is always nostalgic."),
    ("Thinking about volunteering this weekend.", "Volunteering is a great way to give back."),
    ("I read a chapter of my book.", "Reading is such a good habit."),
    ("Thought about getting a houseplant.", "Plants really brighten up a space."),
    ("I listened to a history podcast.", "History podcasts can be surprisingly addictive."),
    ("Tried making homemade ice cream.", "How did it turn out?"),
    ("I cleaned out my garage.", "Garage cleanouts always uncover forgotten stuff."),
    ("Thinking about doing a digital detox.", "A break from screens can be refreshing."),
    ("I saw a rainbow this morning.", "Rainbows always feel like a good sign."),
    ("Read about a new art exhibit in town.", "Art exhibits can be really inspiring."),
    ("Tried a new workout routine.", "Switching things up keeps it interesting."),
    ("I organized my spice rack.", "A well-organized kitchen makes cooking easier."),
    ("Thought about learning origami.", "Origami is such a calming craft."),
    ("I watched a documentary about volcanoes.", "Volcanoes are both terrifying and beautiful."),
    ("Tried a new sandwich shop for lunch.", "New food spots keep lunch interesting."),
    ("I cleaned my windows this weekend.", "Clean windows really let the light in."),
    ("Thinking about starting a journal.", "Journaling can be a great way to process thoughts."),
    ("I heard about a local farmers market.", "Fresh local produce is always worth seeking out."),
]


def _extended_filler_turns(rng: random.Random, count: int) -> list[tuple[str, str]]:
    """Generate filler conversation turns from extended banks for scale scenarios."""
    pool = _DAILY_UPDATES + _MUNDANE_TOPICS + _EXTENDED_TOPICS
    turns = []
    for _ in range(count):
        turn = rng.choice(pool)
        turns.append(turn)
    return turns


def _mixed_filler(rng: random.Random, count: int) -> list[tuple[str, str]]:
    """Mix standard and extended filler for variety."""
    # Use both standard (from scenarios.py) and extended banks
    standard = _filler_turns(rng, count // 2)
    extended = _extended_filler_turns(rng, count - count // 2)
    combined = standard + extended
    rng.shuffle(combined)
    return combined[:count]


# ---------------------------------------------------------------------------
# Marathon Scenario: 1000+ turns
# ---------------------------------------------------------------------------

def generate_marathon_scenario(seed: int = 42) -> LongHorizonScenario:
    """Generate a 1000-turn scenario for scale ablation.

    Hypothesis: At 1000+ turns, RAG's recall degrades (BM25 gets noisier with
    more documents) while Soul's stays stable (selective storage keeps corpus lean).

    Structure:
      - 35 important facts planted across 1000 turns (every ~25-30 turns)
      - Fact categories: life events (8), names (6), dates (5), preferences (6),
        emotional moments (5), professional (5)
      - 7 "callback" facts planted in turns 10-50, never mentioned again
      - 5 "buried" facts surrounded by 50+ turns of filler on both sides
      - 40 test points at the end querying ALL planted facts
      - "Recall by age" metadata on each fact for analysis

    Returns:
        LongHorizonScenario with exactly 1000 turns and 40 recall test points.
    """
    rng = random.Random(seed + 1000)  # Distinct seed from existing scenarios
    turns: list[tuple[str, str]] = []
    test_points: list[TestPoint] = []
    planted_facts: list[tuple[int, str]] = []

    # We build the scenario in phases, each planting facts and filling with noise.
    # Total target: 1000 turns.

    # -----------------------------------------------------------------------
    # Phase 1: Early callback facts (turns 0-49)
    # These are planted early and NEVER mentioned again — tests long-term retention.
    # -----------------------------------------------------------------------

    # Fact 1 (turn 5): User's childhood best friend
    turns.extend(_mixed_filler(rng, 5))
    turns.append((
        "I was just thinking about my childhood best friend, Marcus Rivera.",
        "Childhood friendships are special. How did you two meet?",
    ))
    turns.append((
        "We met in 3rd grade. He moved to Portland years ago but we still text sometimes.",
        "That's a long friendship. It's great you've stayed in touch.",
    ))
    planted_facts.append((5, "User's childhood best friend is Marcus Rivera"))

    # Fact 2 (turn 12): User's blood type
    turns.extend(_mixed_filler(rng, 5))
    turns.append((
        "I had to give blood today. I'm O-negative, the universal donor type.",
        "O-negative is always in demand. That's generous of you.",
    ))
    planted_facts.append((12, "User's blood type is O-negative"))

    # Fact 3 (turn 18): User's grandmother's recipe
    turns.extend(_mixed_filler(rng, 5))
    turns.append((
        "My grandmother used to make this incredible lemon ricotta cake. I have her recipe.",
        "Family recipes are treasures. Have you tried making it yourself?",
    ))
    turns.append((
        "Yeah, I make it every Christmas Eve. It's a family tradition now.",
        "Keeping traditions alive through food is beautiful.",
    ))
    planted_facts.append((18, "User's grandmother's lemon ricotta cake recipe, made every Christmas Eve"))

    # Fact 4 (turn 25): User's fear
    turns.extend(_mixed_filler(rng, 5))
    turns.append((
        "I have this irrational fear of deep water. Like ocean deep, not swimming pools.",
        "Thalassophobia is more common than people think. Has it always been like that?",
    ))
    turns.append((
        "Since I was 8. Almost drowned at the beach.",
        "That's a formative experience. Makes total sense it left a mark.",
    ))
    planted_facts.append((25, "User has thalassophobia (fear of deep water) since age 8"))

    # Fact 5 (turn 32): User's car
    turns.extend(_mixed_filler(rng, 5))
    turns.append((
        "I just got my car back from the shop. My 2019 Subaru Outback needed new brakes.",
        "Subaru Outbacks are solid cars. Brake work isn't cheap though.",
    ))
    planted_facts.append((32, "User drives a 2019 Subaru Outback"))

    # Fact 6 (turn 40): User's anniversary date
    turns.extend(_mixed_filler(rng, 6))
    turns.append((
        "My wedding anniversary is October 3rd. Need to start planning something.",
        "October 3rd — that's coming up! Any ideas for what you'd like to do?",
    ))
    turns.append((
        "Thinking about revisiting the restaurant where we got engaged. It's called Chez Laurent.",
        "Chez Laurent sounds perfect for an anniversary. Very romantic.",
    ))
    planted_facts.append((40, "User's wedding anniversary is October 3rd, got engaged at Chez Laurent"))

    # Fact 7 (turn 48): User's side project
    turns.extend(_mixed_filler(rng, 5))
    turns.append((
        "I've been working on a side project — building a weather station with a Raspberry Pi.",
        "That's a cool maker project! What sensors are you using?",
    ))
    turns.append((
        "Temperature, humidity, barometric pressure. I want to put it on my roof eventually.",
        "A rooftop weather station would give great data. Fun project.",
    ))
    planted_facts.append((48, "User is building a Raspberry Pi weather station"))

    # Pad to exactly 50 turns
    while len(turns) < 50:
        turns.extend(_mixed_filler(rng, 1))
    turns = turns[:50]

    # -----------------------------------------------------------------------
    # Phase 2: Life events and buried facts (turns 50-250)
    # -----------------------------------------------------------------------

    # Fact 8 (turn 75): User started a new job — BURIED (50+ filler before and after)
    turns.extend(_mixed_filler(rng, 25))
    turns.append((
        "Big news — I got a new job at Meridian Labs as a data engineer!",
        "Congratulations! Meridian Labs, that's exciting. Data engineering is such a growing field.",
    ))
    turns.append((
        "Yeah, I start in two weeks. It's a fully remote position which I love.",
        "Remote work is a great perk. You'll save so much commute time.",
    ))
    planted_facts.append((75, "User works at Meridian Labs as a data engineer, fully remote"))

    # 50+ turns of filler after the buried fact
    turns.extend(_mixed_filler(rng, 50))

    # Fact 9 (turn ~128): User's sister's name
    turns.append((
        "My sister Elena is coming to visit next month from Chicago.",
        "That'll be great! How long is Elena staying?",
    ))
    turns.append((
        "About a week. She's bringing her daughter too, my niece Sofia who just turned 4.",
        "A 4-year-old will keep you on your toes! How fun.",
    ))
    planted_facts.append((len(turns) - 2, "User's sister is Elena, lives in Chicago, niece Sofia is 4"))

    turns.extend(_mixed_filler(rng, 20))

    # Fact 10 (turn ~150): User's favorite book
    turns.append((
        "I re-read my all-time favorite book last week — Siddhartha by Hermann Hesse.",
        "Siddhartha is a beautiful book. What draws you to it?",
    ))
    turns.append((
        "The idea that wisdom can't be taught, only experienced. I first read it at 19.",
        "That's a powerful insight. Books hit different at different ages.",
    ))
    planted_facts.append((len(turns) - 2, "User's favorite book is Siddhartha by Hermann Hesse, first read at 19"))

    turns.extend(_mixed_filler(rng, 20))

    # Fact 11 (turn ~172): User's volunteer work
    turns.append((
        "I started volunteering at the Eastside Community Kitchen on Saturday mornings.",
        "That's wonderful. Community kitchens do such important work.",
    ))
    planted_facts.append((len(turns) - 1, "User volunteers at Eastside Community Kitchen on Saturday mornings"))

    turns.extend(_mixed_filler(rng, 25))

    # Fact 12 (turn ~198): User broke their wrist — emotional moment
    turns.append((
        "Terrible day. I fell off my bike and broke my left wrist. At the ER now.",
        "Oh no, I'm so sorry! That sounds really painful. Are they taking care of you?",
    ))
    turns.append((
        "Yeah, getting a cast. Doctor says 6-8 weeks to heal. This is going to mess up my work.",
        "6-8 weeks is tough, but your wrist will heal. Take it easy on yourself.",
    ))
    planted_facts.append((len(turns) - 2, "User broke left wrist falling off bike, 6-8 weeks recovery"))

    turns.extend(_mixed_filler(rng, 20))

    # Fact 13 (turn ~220): User's therapist name
    turns.append((
        "Had my session with Dr. Nadia Okafor today. She's been my therapist for 3 years.",
        "A long-term therapeutic relationship is really valuable. How was the session?",
    ))
    planted_facts.append((len(turns) - 1, "User's therapist is Dr. Nadia Okafor, 3 years"))

    # Pad to 250
    while len(turns) < 250:
        turns.extend(_mixed_filler(rng, 1))
    turns = turns[:250]

    # -----------------------------------------------------------------------
    # Phase 3: Preferences and dates (turns 250-500)
    # -----------------------------------------------------------------------

    turns.extend(_mixed_filler(rng, 25))

    # Fact 14 (turn ~275): Favorite cuisine
    turns.append((
        "If I had to eat one cuisine forever, it'd be Ethiopian. I love injera with everything.",
        "Ethiopian food is incredible. The communal eating style is wonderful too.",
    ))
    planted_facts.append((len(turns) - 1, "User's favorite cuisine is Ethiopian, loves injera"))

    turns.extend(_mixed_filler(rng, 28))

    # Fact 15 (turn ~305): User's birthday — BURIED fact
    turns.append((
        "My birthday is February 14th. Yes, Valentine's Day. My whole life has been about sharing it.",
        "A Valentine's birthday! That must make for interesting celebrations.",
    ))
    planted_facts.append((len(turns) - 1, "User's birthday is February 14th (Valentine's Day)"))

    turns.extend(_mixed_filler(rng, 55))  # 55 turns of filler after = deeply buried

    # Fact 16 (turn ~362): User's pet's name
    turns.append((
        "My golden retriever just did the funniest thing. Bruno stole a whole baguette off the counter.",
        "Bruno! Golden retrievers are food-motivated for sure. That's hilarious.",
    ))
    planted_facts.append((len(turns) - 1, "User has a golden retriever named Bruno"))

    turns.extend(_mixed_filler(rng, 28))

    # Fact 17 (turn ~392): User's college
    turns.append((
        "I got an email from my alma mater, UC Davis. They're doing a fundraiser.",
        "UC Davis has a great alumni network. Are you going to participate?",
    ))
    planted_facts.append((len(turns) - 1, "User went to UC Davis"))

    turns.extend(_mixed_filler(rng, 25))

    # Fact 18 (turn ~419): User's morning routine detail
    turns.append((
        "I've gotten into this routine where I do 20 minutes of yoga every morning before coffee.",
        "Morning yoga is a great way to start. Does it help with your energy levels?",
    ))
    turns.append((
        "Honestly yes. I feel way less stiff. I use the Yoga With Adriene videos on YouTube.",
        "Adriene is so popular for a reason. Her style is really accessible.",
    ))
    planted_facts.append((len(turns) - 2, "User does 20 min morning yoga (Yoga With Adriene on YouTube)"))

    turns.extend(_mixed_filler(rng, 25))

    # Fact 19 (turn ~446): User's music taste
    turns.append((
        "I've been listening to a lot of Khruangbin lately. Their sound is so unique.",
        "Khruangbin has such a distinct vibe — global funk meets psychedelic. Great taste.",
    ))
    planted_facts.append((len(turns) - 1, "User listens to Khruangbin"))

    turns.extend(_mixed_filler(rng, 25))

    # Fact 20 (turn ~473): User's childhood dream — BURIED
    turns.append((
        "When I was a kid I wanted to be a marine biologist. Funny how life takes you elsewhere.",
        "A lot of kids dream about marine biology. What changed for you?",
    ))
    turns.append((
        "I realized I loved computers more than oceans. No regrets though.",
        "Following your real passion is what matters.",
    ))
    planted_facts.append((len(turns) - 2, "User's childhood dream was to be a marine biologist"))

    # Pad to 500
    while len(turns) < 500:
        turns.extend(_mixed_filler(rng, 1))
    turns = turns[:500]

    # -----------------------------------------------------------------------
    # Phase 4: Professional and emotional moments (turns 500-750)
    # -----------------------------------------------------------------------

    turns.extend(_mixed_filler(rng, 25))

    # Fact 21 (turn ~525): User got a raise
    turns.append((
        "Performance review went great. Got a 15% raise and my manager said I'm on track for team lead.",
        "A 15% raise and a path to team lead? That's a strong review. Congratulations!",
    ))
    planted_facts.append((len(turns) - 1, "User got 15% raise, on track for team lead at Meridian Labs"))

    turns.extend(_mixed_filler(rng, 30))

    # Fact 22 (turn ~557): Friend's wedding
    turns.append((
        "My friend Priya is getting married in June. I'm a groomsman!",
        "That's an honor! Priya's wedding in June sounds like it'll be a wonderful time.",
    ))
    planted_facts.append((len(turns) - 1, "User is groomsman at friend Priya's June wedding"))

    turns.extend(_mixed_filler(rng, 28))

    # Fact 23 (turn ~587): Emotional moment — pet health scare
    turns.append((
        "Scary day. Bruno started limping badly and I rushed him to the vet.",
        "That must have been terrifying. Is Bruno okay?",
    ))
    turns.append((
        "Vet says it's a torn CCL ligament. He needs surgery. I'm devastated.",
        "Poor Bruno. CCL surgery is common in dogs and usually goes well. Hang in there.",
    ))
    turns.append((
        "The surgery is $4,500. I'm putting it on my credit card. He's worth it.",
        "Of course he is. Bruno's going to pull through.",
    ))
    planted_facts.append((len(turns) - 3, "Bruno (dog) tore CCL ligament, needs $4,500 surgery"))

    turns.extend(_mixed_filler(rng, 30))

    # Fact 24 (turn ~620): User's dietary restriction
    turns.append((
        "I've been trying to go vegetarian for the past month. It's harder than I thought.",
        "Transitioning to vegetarian takes time. What's been the hardest part?",
    ))
    turns.append((
        "I really miss bacon. But ethically I feel better. Also I'm lactose intolerant so cheese is already out.",
        "Lactose intolerance on top of going vegetarian does limit options. But there are great alternatives now.",
    ))
    planted_facts.append((len(turns) - 2, "User is going vegetarian and is lactose intolerant"))

    turns.extend(_mixed_filler(rng, 25))

    # Fact 25 (turn ~648): User's language learning
    turns.append((
        "I signed up for Portuguese classes! My partner is Brazilian and I want to talk to their family.",
        "Learning Portuguese for your partner's family is such a thoughtful gesture.",
    ))
    turns.append((
        "My partner's name is Camila. Her parents barely speak English so this would mean a lot.",
        "Camila must be really touched that you're doing this.",
    ))
    planted_facts.append((len(turns) - 2, "User is learning Portuguese, partner Camila is Brazilian"))

    turns.extend(_mixed_filler(rng, 25))

    # Fact 26 (turn ~675): User's tech setup
    turns.append((
        "I finally switched from Mac to Linux. Running Ubuntu on a ThinkPad T14s.",
        "Linux on a ThinkPad is a classic developer setup. How's the transition?",
    ))
    planted_facts.append((len(turns) - 1, "User runs Ubuntu Linux on a ThinkPad T14s"))

    turns.extend(_mixed_filler(rng, 25))

    # Fact 27 (turn ~702): Emotional — user's father's health
    turns.append((
        "My dad was diagnosed with Type 2 diabetes last week. I'm worried about him.",
        "I'm sorry to hear that. Type 2 is manageable with the right lifestyle changes. How's he taking it?",
    ))
    turns.append((
        "He's in denial a bit. He's 67 and stubborn. I'm trying to help him adjust his diet.",
        "It takes time to accept. Your support will make a big difference.",
    ))
    planted_facts.append((len(turns) - 2, "User's father (67) diagnosed with Type 2 diabetes"))

    turns.extend(_mixed_filler(rng, 20))

    # Fact 28 (turn ~724): User's home project
    turns.append((
        "We're renovating the guest bedroom into a home office. Picked out a standing desk and everything.",
        "A dedicated home office is a game changer for remote work.",
    ))
    planted_facts.append((len(turns) - 1, "User is renovating guest bedroom into home office with standing desk"))

    # Pad to 750
    while len(turns) < 750:
        turns.extend(_mixed_filler(rng, 1))
    turns = turns[:750]

    # -----------------------------------------------------------------------
    # Phase 5: Late-game facts and final filler (turns 750-960)
    # -----------------------------------------------------------------------

    turns.extend(_mixed_filler(rng, 25))

    # Fact 29 (turn ~775): User's vacation
    turns.append((
        "Booked a trip to Lisbon for September! Two weeks. Can't wait to practice my Portuguese.",
        "Lisbon is gorgeous! Two weeks gives you time to really explore. And what a chance to practice!",
    ))
    planted_facts.append((len(turns) - 1, "User booked 2-week trip to Lisbon in September"))

    turns.extend(_mixed_filler(rng, 30))

    # Fact 30 (turn ~807): User's neighbor
    turns.append((
        "My upstairs neighbor plays trumpet at 11pm. His name is Gerald and I've asked him to stop 5 times.",
        "That's inconsiderate. Have you considered talking to your landlord?",
    ))
    planted_facts.append((len(turns) - 1, "User's upstairs neighbor Gerald plays trumpet at 11pm"))

    turns.extend(_mixed_filler(rng, 28))

    # Fact 31 (turn ~837): User's salary number — BURIED
    turns.append((
        "After the raise my salary is $128,000. Not bad for 5 years in the field.",
        "That's a solid salary for a data engineer with 5 years experience. You should be proud.",
    ))
    planted_facts.append((len(turns) - 1, "User's salary is $128,000, 5 years in data engineering"))

    turns.extend(_mixed_filler(rng, 30))

    # Fact 32 (turn ~869): User's podcast
    turns.append((
        "I started my own podcast! It's called 'Data After Dark' — about data engineering war stories.",
        "Data After Dark — great name! Are you interviewing people or going solo?",
    ))
    turns.append((
        "Mix of both. Already recorded 3 episodes. Hosting on Spotify.",
        "That's impressive — already 3 episodes in. I hope it takes off!",
    ))
    planted_facts.append((len(turns) - 2, "User started podcast 'Data After Dark' about data engineering, on Spotify"))

    turns.extend(_mixed_filler(rng, 25))

    # Fact 33 (turn ~896): User's childhood memory — emotional
    turns.append((
        "I just found an old photo of me and Marcus from summer camp. We were maybe 10. I teared up.",
        "Old photos have such power. Sounds like Marcus means a lot to you.",
    ))
    planted_facts.append((len(turns) - 1, "User has photo with Marcus from summer camp at age 10"))

    turns.extend(_mixed_filler(rng, 25))

    # Fact 34 (turn ~923): User's New Year resolution
    turns.append((
        "My New Year's resolution is to run a half marathon. I've never done more than a 10K.",
        "A half marathon is a great stretch goal from 10K. Are you following a training plan?",
    ))
    turns.append((
        "Using the Hal Higdon plan. Training starts in January.",
        "Hal Higdon is tried and true. You'll be ready by spring.",
    ))
    planted_facts.append((len(turns) - 2, "User's resolution: half marathon, Hal Higdon training plan"))

    turns.extend(_mixed_filler(rng, 20))

    # Fact 35 (turn ~945): User's investment
    turns.append((
        "I put $10,000 into a Vanguard index fund last week. First time investing seriously.",
        "Vanguard index funds are a solid choice for long-term investing. Smart move.",
    ))
    planted_facts.append((len(turns) - 1, "User invested $10,000 in Vanguard index fund"))

    # Pad to 960 (leave room for 40 test turns)
    while len(turns) < 960:
        turns.extend(_mixed_filler(rng, 1))
    turns = turns[:960]

    # -----------------------------------------------------------------------
    # Phase 6: Recall test battery (turns 960-999) — 40 test points
    # -----------------------------------------------------------------------

    recall_battery: list[tuple[str, str, str, str]] = [
        # (query, expected_response, expected_content_substring, category)
        # Category is for "recall by fact age" analysis

        # === Callback facts (planted turns 5-48, never mentioned again) ===
        ("Who was my childhood best friend?",
         "Your childhood best friend is Marcus Rivera.",
         "Marcus Rivera", "callback_early"),

        ("What's my blood type?",
         "You're O-negative, the universal donor type.",
         "O-negative", "callback_early"),

        ("What recipe did I inherit from my grandmother?",
         "Your grandmother's lemon ricotta cake, which you make every Christmas Eve.",
         "lemon ricotta", "callback_early"),

        ("What am I afraid of?",
         "You have thalassophobia — a fear of deep water since you were 8.",
         "deep water", "callback_early"),

        ("What car do I drive?",
         "You drive a 2019 Subaru Outback.",
         "Subaru Outback", "callback_early"),

        ("When is my wedding anniversary?",
         "Your wedding anniversary is October 3rd.",
         "October 3", "callback_early"),

        ("What side project am I building with a Raspberry Pi?",
         "You're building a weather station with a Raspberry Pi.",
         "weather station", "callback_early"),

        # === Mid-range facts (planted turns 75-250) ===
        ("Where do I work and what's my role?",
         "You work at Meridian Labs as a data engineer, fully remote.",
         "Meridian Labs", "mid_range"),

        ("What's my sister's name and where does she live?",
         "Your sister Elena lives in Chicago. Your niece Sofia is 4.",
         "Elena", "mid_range"),

        ("What's my all-time favorite book?",
         "Siddhartha by Hermann Hesse. You first read it at 19.",
         "Siddhartha", "mid_range"),

        ("Where do I volunteer?",
         "You volunteer at the Eastside Community Kitchen on Saturday mornings.",
         "Eastside Community Kitchen", "mid_range"),

        ("What injury did I have recently?",
         "You broke your left wrist falling off your bike.",
         "broke", "mid_range"),

        ("Who is my therapist?",
         "Your therapist is Dr. Nadia Okafor. You've been seeing her for 3 years.",
         "Nadia Okafor", "mid_range"),

        # === Preference facts (planted turns 275-500) ===
        ("What's my favorite type of food?",
         "Ethiopian food — you love injera.",
         "Ethiopian", "preference"),

        ("When is my birthday?",
         "Your birthday is February 14th, Valentine's Day.",
         "February 14", "preference"),

        ("What's my dog's name and breed?",
         "Your golden retriever is named Bruno.",
         "Bruno", "preference"),

        ("Where did I go to college?",
         "You went to UC Davis.",
         "UC Davis", "preference"),

        ("What's my morning exercise routine?",
         "You do 20 minutes of morning yoga, following Yoga With Adriene on YouTube.",
         "yoga", "preference"),

        ("What band have I been listening to a lot?",
         "Khruangbin — you really like their unique sound.",
         "Khruangbin", "preference"),

        ("What did I want to be when I was a kid?",
         "You wanted to be a marine biologist.",
         "marine biologist", "preference"),

        # === Professional facts (planted turns 500-750) ===
        ("How much was my last raise?",
         "You got a 15% raise and you're on track for team lead.",
         "15%", "professional"),

        ("Whose wedding am I in?",
         "You're a groomsman at your friend Priya's June wedding.",
         "Priya", "professional"),

        ("What happened to my dog's leg?",
         "Bruno tore his CCL ligament and needed surgery that cost $4,500.",
         "CCL", "professional"),

        ("Am I vegetarian? Any food restrictions?",
         "You're going vegetarian and you're lactose intolerant.",
         "vegetarian", "professional"),

        ("What language am I learning and why?",
         "You're learning Portuguese because your partner Camila is Brazilian.",
         "Portuguese", "professional"),

        ("What's my partner's name?",
         "Your partner's name is Camila.",
         "Camila", "professional"),

        ("What computer do I use?",
         "You run Ubuntu Linux on a ThinkPad T14s.",
         "ThinkPad", "professional"),

        ("What health issue is my dad dealing with?",
         "Your father was diagnosed with Type 2 diabetes. He's 67.",
         "diabetes", "professional"),

        ("What home renovation am I doing?",
         "You're converting the guest bedroom into a home office with a standing desk.",
         "home office", "professional"),

        # === Late-game facts (planted turns 750-960) ===
        ("What vacation did I book?",
         "You booked a 2-week trip to Lisbon in September.",
         "Lisbon", "late_game"),

        ("What's the deal with my neighbor?",
         "Your upstairs neighbor Gerald plays trumpet at 11pm.",
         "Gerald", "late_game"),

        ("How much do I make?",
         "Your salary is $128,000 after your recent raise.",
         "128,000", "late_game"),

        ("Do I have a podcast?",
         "Yes! Data After Dark — about data engineering war stories, on Spotify.",
         "Data After Dark", "late_game"),

        ("What old photo did I recently find?",
         "A photo of you and Marcus from summer camp when you were about 10.",
         "summer camp", "late_game"),

        ("What's my fitness goal for the new year?",
         "You want to run a half marathon using the Hal Higdon training plan.",
         "half marathon", "late_game"),

        ("Did I start investing?",
         "Yes, you put $10,000 into a Vanguard index fund.",
         "Vanguard", "late_game"),

        # === Cross-reference and synthesis queries ===
        ("Tell me about my family members.",
         "Your sister Elena is in Chicago with your niece Sofia (4). Your partner Camila is Brazilian. Your father (67) has Type 2 diabetes.",
         "Elena", "synthesis"),

        ("What are my hobbies?",
         "You do morning yoga, build Raspberry Pi projects, host the Data After Dark podcast, and are training for a half marathon.",
         "yoga", "synthesis"),

        ("What's the name of the restaurant where I got engaged?",
         "You got engaged at Chez Laurent.",
         "Chez Laurent", "synthesis"),

        ("What breed is my dog and what surgery did he need?",
         "Bruno is a golden retriever who needed CCL ligament surgery.",
         "golden retriever", "synthesis"),
    ]

    for query, expected_response, expected_content, category in recall_battery:
        turn_idx = len(turns)
        turns.append((query, expected_response))
        test_points.append(TestPoint(
            turn_index=turn_idx,
            query=query,
            expected_content=expected_content,
            test_type="recall",
            description=f"Scale recall [{category}]: {expected_content}",
        ))

    # Verify we hit 1000 turns
    assert len(turns) == 1000, f"Expected 1000 turns, got {len(turns)}"

    return LongHorizonScenario(
        scenario_id="marathon_1000",
        name="Marathon Scale Test (1000 turns)",
        description=(
            "1000-turn conversation with 35 facts planted across the full span. "
            "Tests whether RAG recall degrades at scale while Soul's selective storage stays stable. "
            "Includes callback facts (early, never re-mentioned), buried facts (50+ filler on each side), "
            "and synthesis queries requiring cross-referencing multiple facts."
        ),
        turns=turns,
        test_points=test_points,
        planted_facts=planted_facts,
    )


def generate_scale_scenarios(seed: int = 42) -> list[LongHorizonScenario]:
    """Generate all scale-test scenarios (currently just the 1000-turn marathon)."""
    return [generate_marathon_scenario(seed=seed)]
