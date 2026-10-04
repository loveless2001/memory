"""Manually authored from sanitized messages, before any reader inference.

Each fact/control tuple is (source turns, question, proposed answer).
The withdrawal tuple is (turn, topic regex, question, same statement/answer,
different statement/answer). Full-turn coordinates are deliberate: they retain
the editing/request frame and speaker attribution with the quoted assertion.
"""

SPECS = {
    "106": {
        "facts": [
            ([10], "In my original rainy-evening creative-writing passage, which anime supplied the battle scene being drawn, and what were the roommate and cousin watching?", "The passage names My Hero Academia for the battle scene; the roommate and cousin were watching a telenovela marathon."),
            ([18], "In my original anime-convention diary entry, which character and costume version did the narrator cosplay, and whose limited-edition figure did they find?", "The narrator cosplayed Uraraka in her version 2 hero costume and found a limited-edition Bakugo figure."),
        ],
        "control": ([0], "In the original fantasy-commission email, who offers the preview GIF and who is being asked to consider it? Attribute the offer within the email.", "Isabella offers the preview GIF to Marcus."),
        "withdrawal": (172, r"candle|scent|fragrance|aroma", "Do I currently love scented candles in my apartment?", "I love scented candles in my apartment.", "Yes. You explicitly said you love scented candles in your apartment.", "I do not like scented candles in my apartment.", "No. You explicitly said you do not like scented candles in your apartment."),
    },
    "123": {
        "facts": [
            ([24], "In my original passage comparing a board game with rally strategy, where is the apartment, and what are the carved pieces compared to?", "The apartment is in Auckland, and the carved pieces are compared to miniature rally cars ready for the start line."),
            ([38], "In my original email to Farah about returning from home, which town had the writer visited, and what dish did they eat with their parents?", "The writer had visited Kuala Terengganu and ate nasi dagang with their parents."),
        ],
        "control": ([38], "In the original email about the trip home, who gave rally-style driving tips to whom? Keep the attribution within that email.", "Aisyah, the email's writer, gave rally-style driving tips to her brother."),
        "withdrawal": (238, r"techno|festival|music|dance", "Do I currently enjoy techno music festivals?", "I enjoy techno music festivals.", "Yes. You explicitly said you enjoy techno music festivals.", "I do not enjoy techno music festivals.", "No. You explicitly said you do not enjoy techno music festivals."),
    },
    "155": {
        "facts": [
            ([10], "In the original bird-story passage I asked to translate into Vietnamese, where was the book title saved and for which future gathering?", "It was saved in a digital reading log to recommend at the next mothers' reading circle."),
            ([28], "In the original literacy-workshop scheduling email, what change in session start time was requested?", "The requested start time was 10:15 instead of 10:00."),
        ],
        "control": ([126], "In the community-playdate email I received, who says the planning group's wording did not sit right with her, and who is she telling?", "Karen Whitfield says it did not sit right with her, and she is telling Lina Al-Masri."),
        "control_ownership": "named_other",
        "withdrawal": (82, r"electronic|\bDIY\b|\bkit\b|circuit|robot|solder", "Do I currently enjoy DIY electronics kits for fun?", "I enjoy DIY electronics kits for fun.", "Yes. You explicitly said you enjoy DIY electronics kits for fun.", "I do not enjoy DIY electronics kits for fun.", "No. You explicitly said you do not enjoy DIY electronics kits for fun."),
    },
    "2": {
        "facts": [
            ([6], "In my original professional message about a new frontier for cloud computing, which space program supplied the analogy, and which two computing advances were mentioned?", "The analogy used NASA's Artemis program; the two advances were AI integration and distributed systems."),
            ([8], "In my original LinkedIn draft about returning from a cloud summit, what was the event's name and what infrastructure theme stood out?", "It was the Seattle Future of Cloud Summit, and the theme was greener, more energy-efficient infrastructure."),
        ],
        "control": ([28], "Within the original email following the Northwest Cloud Innovation Summit, who offers an in-person or virtual meeting, and to whom?", "Emily offers the meeting options to Jordan."),
        "withdrawal": (122, r"wood|carv|craft|carpent|joiner", "Do I currently practice woodworking as a hobby?", "I practice woodworking as a hobby.", "Yes. You explicitly said you practice woodworking as a hobby.", "I do not practice woodworking as a hobby.", "No. You explicitly said you do not practice woodworking as a hobby."),
    },
    "228": {
        "facts": [
            ([2], "In my original joint-practice email, where did the teams recently meet and which circuit was suggested for the first session?", "They recently met at Willow Springs; Road Atlanta was suggested for the first session."),
            ([12], "In my original personal introduction submitted for Chinese translation, which city and state is the racer from, and which two kinds of races are named?", "The racer is from Charlotte, North Carolina, and the introduction names GT and endurance races."),
        ],
        "control": ([44, 46], "In the Riverside Motors Expo email I received, who finalized the media-highlights slot, and whose slot is it?", "Rebecca finalized the slot for Andre."),
        "control_ownership": "named_other",
        "withdrawal": (136, r"comed|funny|humou?r|sitcom|wholesome", "Do I currently like wholesome comedy shows?", "I like wholesome comedy shows.", "Yes. You explicitly said you like wholesome comedy shows.", "I do not like wholesome comedy shows.", "No. You explicitly said you do not like wholesome comedy shows."),
    },
    "257": {
        "facts": [
            ([10], "In my original apartment reflection submitted for Spanish translation, what three additions are described as making the home welcoming?", "The passage describes plants, art that recalls travels, and furniture with simple, clean lines."),
            ([48], "In my original childhood-meals paragraph submitted for French translation, what two food groups were plentiful and what ingredient was kept low?", "Vegetables and whole grains were plentiful, with very little added sugar."),
        ],
        "control": ([48], "In that childhood-meals paragraph submitted for French translation, who used to say some things run in the family: the writer or someone else?", "The writer attributes that saying to her mother."),
        "withdrawal": (204, r"documentar|stream|film|watch", "Do I currently like watching documentaries on streaming services?", "I like watching documentaries on streaming services.", "Yes. You explicitly said you like watching documentaries on streaming services.", "I do not like watching documentaries on streaming services.", "No. You explicitly said you do not like watching documentaries on streaming services."),
    },
    "267": {
        "facts": [
            ([12], "In my original professional bio for the team's internal site, what kind of models does the analyst build and for what kind of clients?", "The analyst builds portfolio optimization models for fintech clients."),
            ([28], "In my original fintech-conference bio, which city was the visiting partner from, and in which city was the art outing?", "The partner was from Madrid, and the art outing was in Austin."),
        ],
        "control": ([112], "In the project-timeline email I received from a colleague, who had made unexpected family trips back east, and who received that explanation?", "Daniel had made the family trips; Luca received the explanation."),
        "control_ownership": "named_other",
        "withdrawal": (260, r"workshop|skill|class|learn", "Do I currently sign up for skill-building workshops?", "I sign up for skill-building workshops.", "Yes. You explicitly said you sign up for skill-building workshops.", "I do not sign up for skill-building workshops.", "No. You explicitly said you do not sign up for skill-building workshops."),
    },
    "352": {
        "facts": [
            ([22], "In my original portfolio blurb about launching a first mobile title, what three things did the founder learn to balance?", "The founder learned to balance engagement, ethical monetization, and sustainable growth."),
            ([30], "In my original pitch-deck paragraph about monetization beyond ads and IAPs, what offering was tied to in-game events?", "Limited-edition digital art drops were tied to in-game events."),
        ],
        "control": ([38], "Within the original ad-monetization outreach email, who is asking for advice on rewarded video pacing, and whose platform are they addressing?", "Izzy asks Alex for advice and addresses Alex's platform."),
        "withdrawal": (189, r"bike|cycl|ride", "Do I currently enjoy weekend bike rides?", "I enjoy weekend bike rides.", "Yes. You explicitly said you enjoy weekend bike rides.", "I do not enjoy weekend bike rides.", "No. You explicitly said you do not enjoy weekend bike rides."),
    },
    "400": {
        "facts": [
            ([6], "In my original departmental project update, which cinema holdings were overhauled, and into how many intensive bursts was the work divided?", "The Latin American cinema holdings were overhauled, and the work was divided into three intensive bursts."),
            ([10], "In my original workplace reflection submitted for Korean translation, what did the glossy posters promote, and what basic reminders did the narrator still have to give?", "The posters promoted diversity and inclusion; the narrator still had to remind people of their name and how to address them."),
        ],
        "control": ([0], "Within the original cataloging-project email, who proposes shorter shifts or alternating tasks, and who is asked to consider the change?", "Sebastián proposes the changes to Dr. Reynolds."),
        "withdrawal": (136, r"board|game|tabletop|play", "Do I currently like trying new board games with friends?", "I like trying new board games with friends.", "Yes. You explicitly said you like trying new board games with friends.", "I do not like trying new board games with friends.", "No. You explicitly said you do not like trying new board games with friends."),
    },
    "546": {
        "facts": [
            ([0], "In my original downtown-cafe social post, what season's menu was the promo campaign for, and what was the campaign's stated focus?", "It was for a client's autumn menu, and the campaign was safety-focused."),
            ([2], "In my original seasonal-comfort marketing passage, what three practical restaurant touches were suggested?", "Softer lighting, seating layouts that minimize drafts, and staff offering warm beverages upon seating."),
        ],
        "control": ([14], "Within the original email proposing food near Capitol Hill Playhouse, who invites whom to catch up?", "Jasper invites Maya to catch up."),
        "withdrawal": (184, r"Tex|Mex|spic|food|dish|cuisin", "Do I currently enjoy spicy Tex-Mex food regularly?", "I enjoy spicy Tex-Mex food regularly.", "Yes. You explicitly said you enjoy spicy Tex-Mex food regularly.", "I do not enjoy spicy Tex-Mex food.", "No. You explicitly said you do not enjoy spicy Tex-Mex food."),
        "chronology_note": "Later T221 reports greater tolerance for spicier dishes. Tolerance is not enjoyment, and neither Tex-Mex nor regular enjoyment is re-established by that statement. Review this distinction independently.",
    },
    "563": {
        "facts": [
            ([2], "In my original PhD reflection submitted for translation, what comparison describes the restless mind, and what feeling keeps the narrator returning to work?", "The mind is compared to an unsolved equation, and a quiet sort of hope keeps the narrator returning."),
            ([4], "In my original December-kitchen reflection, what concept is explained to the uncle, and what is he stirring?", "The narrator explains a signal processing concept while the uncle stirs a pot of mole."),
        ],
        "control": ([26], "In the email I received about shifting between social worlds, who describes translating jokes for friends and changing conversational rhythm with family, and who is the addressee?", "Luis describes those experiences; Adrian is the addressee."),
        "control_ownership": "named_other",
        "withdrawal": (222, r"archive|album|photo|organiz|file", "Do I currently like organizing personal archives or photo albums?", "I like organizing personal archives or photo albums.", "Yes. You explicitly said you like organizing personal archives or photo albums.", "I do not like organizing personal archives or photo albums.", "No. You explicitly said you do not like organizing personal archives or photo albums."),
    },
    "57": {
        "facts": [
            ([14], "In my original holiday-campaign proposal passage, where do the color accents come from, and what should remain the focal point?", "The accents come from winter landscapes, and the product should remain the focal point."),
            ([20], "In my original Sunday-morning reflection submitted for French translation, what two activities happen together and are credited with sparking ideas?", "Sketching and listening to a design podcast happen together and spark ideas."),
        ],
        "control": ([116], "Within the original community-arts-festival branding email, who asks to review printed boards, and who is being asked to bring a design variation?", "Miguel Alejandro Santos requests a review using printed boards; Alicia is asked to provide a design variation."),
        "withdrawal": (274, r"photo|architect|camera|building", "Do I currently like photographing interesting architecture?", "I like photographing interesting architecture.", "Yes. You explicitly said you like photographing interesting architecture.", "I do not like photographing architecture.", "No. You explicitly said you do not like photographing architecture."),
    },
    "579": {
        "facts": [
            ([18], "In my original waterfront reflection submitted for Portuguese translation, what three neighborhood features made daily life feel connected to the city's story?", "Walkable streets, community gardens, and historic brick buildings."),
            ([82], "In my original weekend-routines passage submitted for German translation, which two kinds of nostalgic objects were at the market stalls?", "Vintage caps and old team pennants."),
        ],
        "control": ([0], "In the waterfront walk-through email I received, who plans to bring their own container and bags, and who is being told they need not pick anything up?", "Karen plans to bring her own container and bags; Jon is told he need not pick anything up."),
        "control_ownership": "named_other",
        "withdrawal": (200, r"recip|cook|kitchen|dish|culinar", "Do I currently like experimenting with new recipes?", "I like experimenting with new recipes.", "Yes. You explicitly said you like experimenting with new recipes.", "I do not like experimenting with new recipes.", "No. You explicitly said you do not like experimenting with new recipes."),
    },
    "593": {
        "facts": [
            ([4], "In my original coastal-town travel notes submitted for Spanish translation, what did the narrator do with locals in the quiet mornings?", "The narrator helped tidy the beach sands before the tide returned."),
            ([26], "In my original Kyoto travel excerpt, what instrument is invoked at the end, and where does the narrator eat after the performance?", "The instrument is a shamisen; the narrator eats at a small riverside eatery."),
        ],
        "control": ([70], "In the brunch-invitation email I received, whose morning green-drink ritual is described, and who is invited to share a slow morning?", "Lena describes her own ritual and invites Amara to share a slow morning."),
        "control_ownership": "named_other",
        "withdrawal": (202, r"hotel|accommodat|lodg|stay|staying|guesthouse|resort|boutique", "What kind of hotel do I currently prefer staying in?", "I prefer staying in boutique hotels.", "You prefer staying in boutique hotels.", "I prefer staying in large chain hotels rather than boutique hotels.", "You prefer staying in large chain hotels rather than boutique hotels."),
        "chronology_note": "During source-only authoring, the initial T208 drumming topic was replaced with T202 hotels because T210 describes a later Salvador dance/drumming experience. Its relationship to the withdrawn preference is ambiguous. No reader output informed this choice.",
    },
    "620": {
        "facts": [
            ([0], "In my original Skylight Loft brochure description, which district contains the property, and what inspired the lounge mural?", "It is in Portland's Alberta Arts District; the mural was inspired by vintage graphic novels."),
            ([4], "In my original coffee-ritual post, what two qualities were to be combined in the new property concept?", "Storybook charm and eco-friendly design."),
        ],
        "control": ([38], "Within the original coastal-property collaboration email, whose ceramic lamps are proposed for whose project?", "Samantha's ceramic lamps are proposed for Arjun's coastal-themed vacation-home project."),
        "withdrawal": (136, r"suppli|corporat|partner|family.owned|company|compan|business", "Do I currently prefer corporate partners or family-owned suppliers?", "I prefer working with corporate partners over family-owned suppliers.", "You prefer corporate partners over family-owned suppliers.", "I prefer working with family-owned suppliers over corporate partners.", "You prefer family-owned suppliers over corporate partners."),
    },
    "637": {
        "facts": [
            ([18], "In my original email about adjusting training for upcoming competitions, how many endurance sessions would move, and to which part of the week?", "Two endurance sessions would move earlier in the week."),
            ([22], "In my original passage about arriving in a city for competition, what sometimes drowned out the musicians, and roughly how many languages did the narrator hear in minutes?", "Passing trams sometimes drowned out the musicians; the narrator heard half a dozen languages."),
        ],
        "control": ([0], "Within the original partnership-proposal email for the 2024 season, who reports the biathlon results and seeks partners, and to whom is the proposal addressed?", "Lars Henriksen reports his results and seeks partners; the proposal is addressed to Ms. Johansen."),
        "withdrawal": (168, r"schedul|unstructur|routine|plan|free.time|training", "What kind of schedule do I currently prefer when not in training?", "When I am not in training, I prefer open, unstructured schedules.", "You prefer open, unstructured schedules when not in training.", "When I am not in training, I prefer a fixed, carefully structured schedule.", "You prefer a fixed, carefully structured schedule when not in training."),
    },
    "701": {
        "facts": [
            ([6], "In my original early-morning garage passage, which brand's interface pinged and where was the race telemetry synced?", "The Yamaha interface pinged, and the telemetry was synced to a laptop."),
            ([76], "In my original email to a mentor about a long-term racing career, which two kinds of work were considered alongside competition?", "More safety consulting and possibly engineering-side projects."),
        ],
        "control": ([20], "Within the original birthday-helmet email, who chose the gift, who is the gift for, and who receives the email?", "Erika chose the gift for Yumi; the email is addressed to Mia."),
        "withdrawal": (184, r"neighbor|explor|local|new.spot|new.place", "Do I currently like exploring new neighborhood spots?", "I like exploring new neighborhood spots.", "Yes. You explicitly said you like exploring new neighborhood spots.", "I do not like exploring new neighborhood spots.", "No. You explicitly said you do not like exploring new neighborhood spots."),
    },
    "824": {
        "facts": [
            ([0], "In my original internal-newsletter bio, what job title is named, and for how many years had the narrator held it?", "The title is Senior Accountant, held for eleven years."),
            ([12], "In the original performance summary I submitted, who is being evaluated, and which particular skill helped colleagues with differing approaches?", "Margaret Otieno is being evaluated; her skill in mediation helped colleagues with differing approaches."),
        ],
        "control": ([197, 199], "In the email from my friend about the early weeks after a child's birth, whose difficult experience is described, and who is being thanked?", "Ruth describes her own experience and thanks Amina."),
        "control_ownership": "named_other",
        "withdrawal": (160, r"board|game|tabletop|play", "Do I currently enjoy board games with friends?", "I enjoy board games with friends.", "Yes. You explicitly said you enjoy board games with friends.", "I do not enjoy board games with friends.", "No. You explicitly said you do not enjoy board games with friends."),
    },
    "843": {
        "facts": [
            ([2], "In my original winter-break class piece, which city was the family visit in, and which city was the stop on the way back?", "The family visit was in Accra, and the stop on the way back was in Dakar."),
            ([24], "In my original guidance-seeking email to a mentor, which university degree and internship organization are named?", "A Real Estate degree at Temple and an internship at Urban Horizons Realty Group."),
        ],
        "control": ([24], "Within the original guidance-seeking email, who is approaching a final semester, and who is asked for career guidance?", "Kwame Mensah is approaching his final semester and asks Professor Jacobs for guidance."),
        "withdrawal": (156, r"cloth|colou?r|muted|earth|wear|fashion|blazer|shirt", "What clothing colors do I currently prefer?", "I prefer muted earth tones in my clothing.", "You prefer muted earth tones in your clothing.", "I prefer bright primary colors in my clothing rather than muted earth tones.", "You prefer bright primary colors rather than muted earth tones."),
    },
    "972": {
        "facts": [
            ([2], "In my original Thai paragraph submitted for Ukrainian translation, what occupation and city does the narrator state?", "The narrator says they work as a tour guide in Bangkok."),
            ([14], "In my original market passage submitted for Italian translation, what flavors are described alongside the warm corn tortillas?", "Tangy lime, fresh cilantro, and a fiery spicy kick."),
        ],
        "control": ([30], "Within the original riverside thank-you email, who stopped to admire silver bracelets on the way home, and who had taken that person around the riverside?", "Lila stopped to admire the bracelets; May had taken her around the riverside."),
        "withdrawal": (234, r"fashion|cloth|wear|bold|form.fitting|style", "What clothing style do I currently prefer?", "I prefer bold, form-fitting fashion styles.", "You prefer bold, form-fitting fashion styles.", "I prefer understated, loose-fitting clothes rather than bold, form-fitting styles.", "You prefer understated, loose-fitting clothes rather than bold, form-fitting styles."),
    },
}
