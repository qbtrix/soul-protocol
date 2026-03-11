# scenarios.py — Long-horizon conversation scenario generator for ablation study.
# Created: 2026-03-11
# Generates 3 scenario types (100-200 turns each) to prove the psychology
# stack creates wider gaps at scale: significance gating, activation decay,
# personality modulation, and somatic markers compound over many turns.
#
# Scenario A: "Life Updates Over Time" — long-range recall, emotional arc tracking
# Scenario B: "Emotional Rollercoaster" — somatic marker effectiveness, emotional continuity
# Scenario C: "Adversarial Burial" — recall precision under noise, significance gating vs RAG

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class TestPoint:
    """A turn index where we measure recall or emotional metrics."""

    turn_index: int
    query: str
    expected_content: str  # substring that should appear in recalled memories
    test_type: str  # "recall", "emotion", "bond"
    description: str = ""


@dataclass
class LongHorizonScenario:
    """A 100+ turn scenario with marked test points."""

    scenario_id: str
    name: str
    description: str
    turns: list[tuple[str, str]]  # (user_input, agent_output) pairs
    test_points: list[TestPoint]
    planted_facts: list[tuple[int, str]]  # (turn_index, fact_content)

    @property
    def turn_count(self) -> int:
        return len(self.turns)


# ---------------------------------------------------------------------------
# Filler conversation banks (deterministic via seeded RNG)
# ---------------------------------------------------------------------------

_WEATHER_CHAT = [
    ("Nice weather today, isn't it?", "It really is! Perfect day to get outside."),
    ("It's been raining all week.", "I hope it clears up soon for you."),
    ("The forecast says snow tomorrow.", "Stay warm and bundle up!"),
    ("I love sunny days like this.", "Sunshine definitely lifts the mood."),
    ("It's so hot out there today.", "Make sure to stay hydrated!"),
]

_SMALL_TALK = [
    ("What do you think about that?", "I think it's an interesting perspective."),
    ("Just checking in.", "Good to hear from you! How's your day?"),
    ("Nothing much going on today.", "Sometimes a quiet day is exactly what you need."),
    ("I had a pretty boring lunch.", "Even mundane meals are part of the routine."),
    ("Saw a funny meme earlier.", "Those little moments of humor make the day better."),
    ("Traffic was terrible this morning.", "That sounds annoying. Hopefully tomorrow's smoother."),
    ("I need to do laundry tonight.", "The never-ending cycle of chores!"),
    ("Watched some TV last night.", "Anything good on?"),
    ("My phone battery died today.", "That's always inconvenient."),
    ("I should probably clean my desk.", "A tidy workspace can help with focus."),
    ("Had coffee with a coworker.", "Nice! Social breaks are great."),
    ("I forgot my umbrella today.", "Murphy's law in action."),
    ("Need to get groceries later.", "Making a list always helps me remember everything."),
    ("The meeting ran long today.", "Long meetings can really drain your energy."),
    ("I tried a new restaurant.", "How was it? Always fun to explore new places."),
    ("My neighbor's dog was barking all night.", "That sounds exhausting. Hope you got some rest."),
    ("Thinking about rearranging my room.", "A fresh layout can feel like a fresh start."),
    ("I went for a short walk.", "Even a brief walk can clear the mind."),
    ("Just had some tea.", "A nice cup of tea is always comforting."),
    ("Weekend plans are still up in the air.", "Sometimes it's nice to keep things open."),
]

_GENERIC_TOPICS = [
    ("I was reading about space today.", "Space is fascinating. What caught your eye?"),
    ("Do you know much about gardening?", "I know a bit! What are you thinking of growing?"),
    ("I've been listening to a lot of podcasts.", "Podcasts are great. Any favorites?"),
    ("Thinking about learning to cook more.", "Cooking is a great skill to develop."),
    ("I started organizing old photos.", "That's a nice trip down memory lane."),
    ("My friend recommended a book to me.", "That's always a good sign. What's the book?"),
    ("I've been trying to drink more water.", "Staying hydrated is so important."),
    ("Watched a documentary about the ocean.", "The ocean is endlessly fascinating."),
    ("I think I want to learn a new language.", "That's a great goal! Any language in mind?"),
    ("I found an old journal from college.", "Reading old journals can be really eye-opening."),
]


def _filler_turns(rng: random.Random, count: int) -> list[tuple[str, str]]:
    """Generate filler conversation turns from the banks."""
    pool = _WEATHER_CHAT + _SMALL_TALK + _GENERIC_TOPICS
    turns = []
    for _ in range(count):
        turn = rng.choice(pool)
        turns.append(turn)
    return turns


# ---------------------------------------------------------------------------
# Scenario A: Life Updates Over Time
# ---------------------------------------------------------------------------

def generate_life_updates(seed: int = 42) -> LongHorizonScenario:
    """Generate a 160-turn scenario simulating life updates over weeks/months.

    Structure:
      Turn 1-20: User starts a new job at TechCorp as a product manager
      Turn 21-50: User mentions relationship struggles with partner Alex
      Turn 51-80: User picks up hiking as a new hobby
      Turn 81-100: Mixed daily conversation + subtle callbacks
      Turn 101-120: User references the job from early turns (buried callback)
      Turn 121-150: More conversation
      Turn 151-160: Explicit recall test questions
    """
    rng = random.Random(seed)
    turns: list[tuple[str, str]] = []
    test_points: list[TestPoint] = []
    planted_facts: list[tuple[int, str]] = []

    # --- Phase 1: New job (turns 0-19) ---
    job_turns = [
        ("I just got a new job!", "That's exciting! Tell me more about it."),
        ("I'm going to be a product manager at TechCorp.", "Product management at TechCorp, that's a great role! How are you feeling about it?"),
        ("I start next Monday. Pretty nervous honestly.", "First day nerves are totally normal. You'll do great."),
        ("My salary is way better than my last job.", "That's a nice upgrade. Financial security makes a big difference."),
        ("I'll be managing a team of 8 engineers.", "Leading a team of 8 is a solid responsibility. Are you looking forward to it?"),
        ("My boss is named Sarah Chen.", "It's good to know your boss. Hopefully you two click."),
        ("The office is downtown, about a 30-minute commute.", "That's a reasonable commute. Do you drive or take transit?"),
        ("I'm taking the train. Trying to be more eco-friendly.", "Good on you! Plus you can read or listen to something on the way."),
        ("They use Jira for project management.", "Jira is pretty standard. Are you familiar with it?"),
        ("Yeah I used it at my last job too. Not a fan but it works.", "It gets the job done even if it's not the most exciting tool."),
    ]
    turns.extend(job_turns)
    planted_facts.append((1, "User is a product manager at TechCorp"))
    planted_facts.append((4, "User manages a team of 8 engineers"))
    planted_facts.append((5, "User's boss is named Sarah Chen"))

    # Fill to 20 turns
    turns.extend(_filler_turns(rng, 10))

    # --- Phase 2: Relationship struggles (turns 20-49) ---
    relationship_turns = [
        ("Things have been tough with my partner Alex lately.", "I'm sorry to hear that. What's been going on?"),
        ("We've been arguing a lot about finances.", "Money disagreements are one of the most common stressors in relationships."),
        ("Alex wants to buy a house but I think we should wait.", "That's a big decision. Both perspectives make sense."),
        ("I feel like we're not on the same page anymore.", "That misalignment can be really stressful. Have you talked about it openly?"),
        ("We tried couples counseling last week.", "That takes courage. How did it go?"),
        ("It was okay. The therapist gave us some communication exercises.", "Communication exercises can really help if you both commit to them."),
        ("Alex's birthday is coming up in March. I need gift ideas.", "What kinds of things does Alex enjoy?"),
        ("Alex loves cooking and vintage vinyl records.", "A nice cookbook or a rare vinyl could be really meaningful."),
        ("I think I'll get Alex a vinyl record from our first date concert.", "That's incredibly thoughtful and personal."),
        ("We actually went to see The National on our first date.", "The National is a great band. That vinyl would be such a sentimental gift."),
    ]
    turns.extend(relationship_turns)
    planted_facts.append((20, "User's partner is named Alex"))
    planted_facts.append((27, "Alex loves cooking and vintage vinyl records"))
    planted_facts.append((29, "User and Alex saw The National on their first date"))

    # Fill to 50 turns
    turns.extend(_filler_turns(rng, 20))

    # --- Phase 3: New hobby - hiking (turns 50-79) ---
    hobby_turns = [
        ("I started hiking last weekend!", "That's awesome! Where did you go?"),
        ("We hiked Mount Tamalpais. The views were incredible.", "Mount Tamalpais is beautiful. How long was the hike?"),
        ("About 4 hours round trip. My legs are still sore.", "That's a decent hike! The soreness means you got a good workout."),
        ("I think I'm going to make it a weekly thing.", "Having a regular outdoor activity is great for mental health."),
        ("I bought new hiking boots. Salomon X Ultra.", "Salomon makes great hiking boots. Good investment."),
        ("I want to do Half Dome eventually.", "Half Dome is a bucket list hike. That's an ambitious goal!"),
        ("My friend Jake is an experienced hiker. He's going to train me.", "Having a mentor makes all the difference in hiking."),
        ("Jake said I should aim for Half Dome by September.", "That gives you several months to build up. Totally doable."),
        ("I downloaded the AllTrails app to track my hikes.", "AllTrails is perfect for finding new trails and tracking progress."),
        ("I did a sunrise hike this morning. So peaceful.", "Sunrise hikes are magical. The early wake-up is worth it."),
    ]
    turns.extend(hobby_turns)
    planted_facts.append((50, "User started hiking"))
    planted_facts.append((54, "User bought Salomon X Ultra hiking boots"))
    planted_facts.append((55, "User wants to hike Half Dome"))
    planted_facts.append((56, "User's friend Jake is training them for hiking"))

    # Fill to 80 turns
    turns.extend(_filler_turns(rng, 20))

    # --- Phase 4: Mixed daily + subtle callbacks (turns 80-99) ---
    callback_turns = [
        ("Work has been crazy busy lately.", "Product management can get intense. How's the team handling it?"),
        ("The engineers are great but we have a tight deadline.", "Tight deadlines with a good team can actually be energizing."),
        ("Sarah pushed back the deadline by a week, which helps.", "Good leadership from Sarah. A week can make a big difference."),
        ("Alex and I had a good weekend for once.", "That's really nice to hear. What did you do?"),
        ("We went hiking together! Alex actually enjoyed it.", "That's wonderful that you could share your hobby together."),
    ]
    turns.extend(callback_turns)
    turns.extend(_filler_turns(rng, 15))

    # --- Phase 5: Buried callback to early turns (turns 100-119) ---
    callback_turns_2 = [
        ("Remember when I first told you about my job?", "Of course! You were nervous about starting as a product manager at TechCorp."),
        ("It's been 3 months now. Time flies.", "Three months already! How has it been?"),
        ("I actually got positive feedback from Sarah in my review.", "That's great! Your hard work is being recognized."),
        ("The team shipped the project on time.", "Amazing! Leading 8 engineers to an on-time delivery is a real achievement."),
        ("I'm thinking about what's next career-wise.", "It's smart to think ahead. Any directions you're considering?"),
    ]
    turns.extend(callback_turns_2)

    # Test points for buried callbacks
    test_points.append(TestPoint(
        turn_index=100,
        query="What job did the user start?",
        expected_content="product manager",
        test_type="recall",
        description="Buried callback: job from turn 1",
    ))
    test_points.append(TestPoint(
        turn_index=100,
        query="Where does the user work?",
        expected_content="TechCorp",
        test_type="recall",
        description="Buried callback: company from turn 1",
    ))

    turns.extend(_filler_turns(rng, 15))

    # --- Phase 6: More conversation (turns 120-149) ---
    turns.extend(_filler_turns(rng, 30))

    # --- Phase 7: Explicit recall tests (turns 150-159) ---
    recall_turns = [
        ("Do you remember my partner's name?", "Your partner's name is Alex."),
        ("What hobby did I pick up recently?", "You started hiking! You even want to do Half Dome."),
        ("Who is training me for hiking?", "Your friend Jake is helping you train."),
        ("What was my first big hike?", "You hiked Mount Tamalpais — about 4 hours round trip."),
        ("What concert did Alex and I go to on our first date?", "You saw The National on your first date."),
        ("What boots did I buy for hiking?", "You got Salomon X Ultra hiking boots."),
        ("Who is my boss at work?", "Your boss is Sarah Chen."),
        ("How many people are on my team?", "You manage a team of 8 engineers."),
        ("What's Alex's favorite hobby?", "Alex loves cooking and vintage vinyl records."),
        ("What app do I use for hiking?", "You use AllTrails to track your hikes."),
    ]
    turns.extend(recall_turns)

    # Test points for explicit recall
    for i, (query, _) in enumerate(recall_turns):
        expected_map = {
            0: "Alex",
            1: "hiking",
            2: "Jake",
            3: "Tamalpais",
            4: "National",
            5: "Salomon",
            6: "Sarah Chen",
            7: "8 engineers",
            8: "cooking",
            9: "AllTrails",
        }
        test_points.append(TestPoint(
            turn_index=150 + i,
            query=query,
            expected_content=expected_map[i],
            test_type="recall",
            description=f"Explicit recall test {i + 1}",
        ))

    return LongHorizonScenario(
        scenario_id="life_updates",
        name="Life Updates Over Time",
        description="Simulates a user sharing life events over weeks/months with buried callbacks",
        turns=turns,
        test_points=test_points,
        planted_facts=planted_facts,
    )


# ---------------------------------------------------------------------------
# Scenario B: Emotional Rollercoaster
# ---------------------------------------------------------------------------

def generate_emotional_rollercoaster(seed: int = 42) -> LongHorizonScenario:
    """Generate a 150-turn scenario with intense emotional peaks and valleys.

    Tests somatic marker effectiveness and emotional continuity.
    Significance gating should store emotional peaks, not mundane turns.

    Structure:
      Turn 0-19:   Happy phase (got promoted, celebrating)
      Turn 20-39:  Sad phase (pet passed away, grief)
      Turn 40-59:  Angry phase (got scammed, dealing with bureaucracy)
      Turn 60-79:  Mixed phase (new beginning, cautious optimism)
      Turn 80-99:  Filler with occasional emotional callbacks
      Turn 100-119: Recovery and growth
      Turn 120-149: Emotional recall tests
    """
    rng = random.Random(seed + 100)
    turns: list[tuple[str, str]] = []
    test_points: list[TestPoint] = []
    planted_facts: list[tuple[int, str]] = []

    # --- Happy phase (turns 0-19) ---
    happy_turns = [
        ("I GOT PROMOTED!!!", "CONGRATULATIONS! That's incredible news! Tell me everything!"),
        ("I'm now Senior Director of Engineering!", "Senior Director! That's a massive step up. You must be thrilled."),
        ("My team threw me a surprise party.", "That's so sweet! Your team clearly appreciates you."),
        ("I'm getting a 40% raise too.", "That's a significant bump. You've earned it."),
        ("I called my parents to tell them. Mom cried happy tears.", "Those moments with family are priceless."),
        ("My dad said he's proud of me. He never says stuff like that.", "That must mean the world coming from him."),
        ("I feel like all the hard work finally paid off.", "It absolutely did. This is your moment."),
        ("I'm taking the team out for dinner to celebrate.", "What a generous way to share the joy."),
        ("We went to this amazing Italian place. Everyone had a blast.", "Celebrating together strengthens those team bonds."),
        ("I feel on top of the world right now.", "Soak it in. You deserve every bit of this happiness."),
    ]
    turns.extend(happy_turns)
    planted_facts.append((1, "User got promoted to Senior Director of Engineering"))
    planted_facts.append((3, "User received a 40% raise"))
    turns.extend(_filler_turns(rng, 10))

    # --- Sad phase (turns 20-39) ---
    sad_turns = [
        ("I don't know how to say this... my dog Biscuit passed away yesterday.", "I'm so deeply sorry. Losing a pet is losing a family member."),
        ("He was 14 years old. I had him since college.", "14 years of love and memories. Biscuit was lucky to have you."),
        ("I can't stop crying. The house feels so empty.", "Grief takes time. Let yourself feel whatever comes."),
        ("I keep looking at his bed expecting him to be there.", "Those little reminders are the hardest part."),
        ("My coworkers sent flowers. That was really kind.", "It's comforting when people show they care."),
        ("I found a photo of Biscuit as a puppy. He was so tiny.", "Puppy photos are treasures. Hold onto those memories."),
        ("I don't think I can get another dog for a while.", "There's no rush. Take all the time you need."),
        ("The vet said he didn't suffer. That helps a little.", "Knowing he was at peace is some comfort."),
        ("I planted a little tree in the backyard for him.", "That's a beautiful tribute. He'll always be part of your home."),
        ("Some days are harder than others.", "Grief isn't linear. The hard days don't erase the progress."),
    ]
    turns.extend(sad_turns)
    planted_facts.append((20, "User's dog Biscuit passed away at age 14"))
    planted_facts.append((28, "User planted a tree in memory of Biscuit"))
    turns.extend(_filler_turns(rng, 10))

    # --- Angry phase (turns 40-59) ---
    angry_turns = [
        ("I am FURIOUS. Someone hacked my bank account.", "That's terrible! Have you contacted your bank?"),
        ("They stole $3,000 before I noticed.", "That's a significant amount. Banks usually have fraud protection."),
        ("The bank is being incredibly unhelpful.", "That's infuriating when you need support the most."),
        ("They keep transferring me to different departments.", "Bureaucratic runaround when you're already stressed is the worst."),
        ("I had to file a police report too.", "Good that you're documenting everything officially."),
        ("I spent 4 hours on the phone today. FOUR HOURS.", "That's exhausting. I'm sorry you're dealing with this."),
        ("They're saying it could take 90 days to investigate.", "90 days is a long time to wait when it's your money."),
        ("I've changed all my passwords. I feel violated.", "Having your security breached is genuinely traumatic."),
        ("My credit card was compromised too.", "This is getting worse. Make sure to freeze your credit."),
        ("I'm so angry I can barely sleep.", "The stress and anger are completely understandable."),
    ]
    turns.extend(angry_turns)
    planted_facts.append((40, "User's bank account was hacked, $3,000 stolen"))
    planted_facts.append((46, "Bank investigation takes 90 days"))
    turns.extend(_filler_turns(rng, 10))

    # --- Mixed / new beginning phase (turns 60-79) ---
    mixed_turns = [
        ("I've been thinking... maybe this year is about growth through adversity.", "That's a powerful way to reframe what you've been through."),
        ("The bank finally started the refund process.", "That's a relief! Progress at last."),
        ("I adopted a cat. Her name is Mochi.", "Mochi! What a sweet name. Cats bring such comfort."),
        ("She's a calico and already rules the house.", "Calicos are known for their personality! She sounds perfect."),
        ("The promotion is going well. I'm settling into the new role.", "Glad to hear the professional side is stabilizing."),
        ("I started therapy to deal with everything this year.", "That's a really healthy and brave decision."),
        ("My therapist says I have a pattern of not asking for help.", "Recognizing patterns is the first step to changing them."),
        ("I'm trying to be more vulnerable with people.", "Vulnerability is actually a sign of strength."),
        ("Alex and I are doing better. The counseling helped.", "That's wonderful. It takes work from both sides."),
        ("I feel cautiously optimistic about the future.", "Cautious optimism is a healthy place to be."),
    ]
    turns.extend(mixed_turns)
    planted_facts.append((62, "User adopted a calico cat named Mochi"))
    planted_facts.append((65, "User started therapy"))
    turns.extend(_filler_turns(rng, 10))

    # --- Filler with emotional callbacks (turns 80-99) ---
    callback_emotional = [
        ("Mochi knocked over my coffee this morning. Classic cat.", "Mochi keeping you on your toes!"),
        ("I got the bank refund! All $3,000 back.", "Finally! Justice served. That must be such a relief."),
        ("I visited Biscuit's tree today. It's growing.", "That's bittersweet and beautiful."),
        ("Had a great day at work. The team hit a milestone.", "Your leadership is making a real difference."),
        ("Feeling grateful today despite everything.", "Gratitude after hardship shows real resilience."),
    ]
    turns.extend(callback_emotional)
    turns.extend(_filler_turns(rng, 15))

    # --- Recovery and growth (turns 100-119) ---
    turns.extend(_filler_turns(rng, 20))

    # --- Emotional recall tests (turns 120-149) ---
    emotional_recall = [
        ("What was the happiest thing that happened to me this year?", "Your promotion to Senior Director of Engineering was a high point!"),
        ("What's the saddest thing I shared with you?", "Losing your dog Biscuit was heartbreaking. He was 14."),
        ("What made me really angry recently?", "Your bank account getting hacked and losing $3,000 was infuriating."),
        ("What's my cat's name?", "Your cat's name is Mochi — a calico who rules the house."),
        ("Did I plant anything special?", "You planted a tree in your backyard in memory of Biscuit."),
        ("How much was stolen from my account?", "Someone stole $3,000 from your bank account."),
        ("What did I start to deal with my tough year?", "You started therapy, which was a really brave decision."),
        ("How big was my raise?", "You got a 40% raise with your promotion."),
    ]
    turns.extend(emotional_recall)

    # Add test points for emotional recall
    recall_expected = [
        "Senior Director",
        "Biscuit",
        "hacked",
        "Mochi",
        "tree",
        "3,000",
        "therapy",
        "40%",
    ]
    for i, ((query, _), expected) in enumerate(zip(emotional_recall, recall_expected)):
        test_points.append(TestPoint(
            turn_index=120 + i,
            query=query,
            expected_content=expected,
            test_type="recall",
            description=f"Emotional recall test {i + 1}",
        ))

    # Emotional valence test points (check at phase boundaries)
    test_points.append(TestPoint(
        turn_index=10,
        query="How is the user feeling?",
        expected_content="happy",
        test_type="emotion",
        description="Should detect positive emotion during promotion phase",
    ))
    test_points.append(TestPoint(
        turn_index=25,
        query="How is the user feeling?",
        expected_content="sad",
        test_type="emotion",
        description="Should detect negative emotion during grief phase",
    ))
    test_points.append(TestPoint(
        turn_index=45,
        query="How is the user feeling?",
        expected_content="angry",
        test_type="emotion",
        description="Should detect negative emotion during anger phase",
    ))

    # Fill to 150
    remaining = 150 - len(turns)
    if remaining > 0:
        turns.extend(_filler_turns(rng, remaining))

    return LongHorizonScenario(
        scenario_id="emotional_rollercoaster",
        name="Emotional Rollercoaster",
        description="Intense emotional journey with peaks and valleys over 150 turns",
        turns=turns,
        test_points=test_points,
        planted_facts=planted_facts,
    )


# ---------------------------------------------------------------------------
# Scenario C: Adversarial Burial
# ---------------------------------------------------------------------------

def generate_adversarial_burial(seed: int = 42) -> LongHorizonScenario:
    """Generate a 160-turn scenario that buries 5 specific facts under noise.

    Plant 5 facts in turns 0-9, then fill turns 10-149 with varied but
    unrelated conversation. At turns 150-159, ask about each planted fact.

    Tests recall precision under noise and significance gating vs. RAG.
    RAG-only should drown in 140+ stored conversations while significance
    gating should keep the important facts accessible.
    """
    rng = random.Random(seed + 200)
    turns: list[tuple[str, str]] = []
    test_points: list[TestPoint] = []
    planted_facts: list[tuple[int, str]] = []

    # --- Plant 5 specific facts (turns 0-9) ---
    fact_turns = [
        # Fact 1: User's mother's birthday
        ("My mother's birthday is July 15th.", "I'll remember that! July 15th for your mom's birthday."),
        ("She'll be turning 65 this year.", "A milestone birthday! Are you planning something special?"),
        # Fact 2: User's allergy
        ("Oh by the way, I'm severely allergic to shellfish.", "That's important to know. Shellfish allergies can be serious."),
        ("I had a bad reaction last year and ended up in the ER.", "That sounds scary. Do you carry an EpiPen?"),
        # Fact 3: User's dream destination
        ("I've always dreamed of visiting Kyoto in cherry blossom season.", "Kyoto during sakura season is breathtaking. That's a wonderful dream."),
        # Fact 4: User's childhood pet
        ("When I was a kid, I had a goldfish named Captain Sparkles.", "Captain Sparkles! That's an amazing name for a goldfish."),
        # Fact 5: User's secret talent
        ("Here's something most people don't know — I can play the theremin.", "The theremin! That's such a unique and fascinating instrument."),
        ("I learned it from YouTube videos during the pandemic.", "Self-taught theremin from YouTube. That's dedication."),
        # Padding turns with minor info
        ("It's a weird hobby but I love it.", "Unique hobbies make life more interesting."),
        ("Anyway, enough about me for now.", "I'm always happy to learn more about you."),
    ]
    turns.extend(fact_turns)

    planted_facts.append((0, "User's mother's birthday is July 15th"))
    planted_facts.append((2, "User is severely allergic to shellfish"))
    planted_facts.append((4, "User dreams of visiting Kyoto during cherry blossom season"))
    planted_facts.append((5, "User had a goldfish named Captain Sparkles"))
    planted_facts.append((6, "User can play the theremin"))

    # --- Fill turns 10-149 with 140 turns of varied noise ---
    # Mix of different topic banks to create diverse noise
    noise_topics = [
        ("I read an article about Mars colonization today.", "Space exploration is advancing rapidly."),
        ("The stock market was volatile today.", "Markets can be unpredictable."),
        ("I learned a new recipe for sourdough bread.", "Sourdough is a rewarding baking project."),
        ("My car needs an oil change.", "Regular maintenance keeps it running well."),
        ("I've been thinking about redecorating my living room.", "What style are you drawn to?"),
        ("There's a new coffee shop downtown.", "New coffee spots are always worth checking out."),
        ("I tried yoga for the first time.", "How did you find the experience?"),
        ("My internet has been really slow lately.", "Slow internet is so frustrating."),
        ("I'm thinking of getting a standing desk.", "Standing desks can be great for posture."),
        ("Finished a puzzle with 1000 pieces.", "That takes serious patience and focus."),
        ("I saw a hawk in my backyard today.", "Hawks are magnificent birds."),
        ("Been learning about cryptocurrency.", "It's a complex but interesting space."),
        ("Tried making sushi at home. It was messy.", "Homemade sushi gets better with practice."),
        ("The gym was packed today.", "Peak hours can be frustrating."),
        ("I need to renew my passport.", "Good to stay ahead of that."),
        ("My favorite team won last night.", "That must have been exciting to watch!"),
        ("I've been sleeping terribly this week.", "Poor sleep really affects everything."),
        ("Thinking about volunteering at the animal shelter.", "That's a wonderful way to give back."),
        ("My dishwasher broke.", "Appliance issues are always inconvenient."),
        ("I signed up for a 5K run.", "That's a great fitness goal!"),
        ("The sunset was beautiful today.", "Nature's artwork is the best."),
        ("I'm considering switching phone carriers.", "Worth comparing plans carefully."),
        ("My coworker brought homemade cookies.", "Coworkers who bake are the best."),
        ("I finally finished that book I was reading.", "How was the ending?"),
        ("Thinking about learning chess.", "Chess is wonderful for the mind."),
        ("I went to a farmers market this weekend.", "Fresh produce is the best."),
        ("My sister is visiting next month.", "That'll be nice to catch up."),
        ("I found a $20 bill in an old jacket.", "Always a pleasant surprise!"),
        ("The leaves are starting to change color.", "Fall foliage is so pretty."),
        ("I've been watching a lot of documentaries.", "Documentaries can be really eye-opening."),
    ]

    for _ in range(140):
        turn = rng.choice(noise_topics)
        turns.append(turn)

    # --- Recall tests (turns 150-159) ---
    recall_tests = [
        ("When is my mother's birthday?", "Your mother's birthday is July 15th."),
        ("What am I allergic to?", "You're severely allergic to shellfish."),
        ("What's my dream travel destination?", "You've always wanted to visit Kyoto during cherry blossom season."),
        ("What was my childhood pet's name?", "You had a goldfish named Captain Sparkles."),
        ("What unusual instrument can I play?", "You can play the theremin! You taught yourself from YouTube."),
        ("How old will my mother be this year?", "She'll be turning 65 this year."),
        ("What happened when I ate shellfish?", "You had a bad reaction and ended up in the ER."),
        ("How did I learn the theremin?", "You learned it from YouTube videos during the pandemic."),
        ("What season do I want to visit Kyoto?", "Cherry blossom season — sakura season in Kyoto."),
        ("What kind of pet was Captain Sparkles?", "Captain Sparkles was a goldfish you had as a kid."),
    ]
    turns.extend(recall_tests)

    recall_expected = [
        "July 15",
        "shellfish",
        "Kyoto",
        "Captain Sparkles",
        "theremin",
        "65",
        "ER",
        "YouTube",
        "cherry blossom",
        "goldfish",
    ]
    for i, ((query, _), expected) in enumerate(zip(recall_tests, recall_expected)):
        test_points.append(TestPoint(
            turn_index=150 + i,
            query=query,
            expected_content=expected,
            test_type="recall",
            description=f"Adversarial burial recall test {i + 1}: fact planted in first 10 turns, buried under 140 turns of noise",
        ))

    return LongHorizonScenario(
        scenario_id="adversarial_burial",
        name="Adversarial Burial",
        description="5 facts buried under 140 turns of noise, then tested for recall",
        turns=turns,
        test_points=test_points,
        planted_facts=planted_facts,
    )


# ---------------------------------------------------------------------------
# Convenience: generate all scenarios
# ---------------------------------------------------------------------------

ALL_SCENARIO_GENERATORS = {
    "life_updates": generate_life_updates,
    "emotional_rollercoaster": generate_emotional_rollercoaster,
    "adversarial_burial": generate_adversarial_burial,
}


def generate_all_scenarios(seed: int = 42) -> list[LongHorizonScenario]:
    """Generate all three long-horizon scenarios."""
    return [gen(seed=seed) for gen in ALL_SCENARIO_GENERATORS.values()]
